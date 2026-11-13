"""Asking the tax assistant a question (feature 006, tasks T013 and T017; research R5-R7).

In order: refuse before the corpus exists; count the question against the user's hourly limit
and the whole app's daily cap (both before any AI is used); search; refuse below the relevance
cut-off without asking the AI; ask Gemini to answer from the passages found; check its reply in
plain code; then answer with citations, or refuse. Nothing about the question is stored but who
asked and when (FR-009). Every result carries the practitioner label (FR-008).
"""

import asyncio
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from sqlalchemy import delete, exists, func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.answer import AnswerError, ModelAnswer
from app.rag.checks import checked_citations, written_in_english
from app.rag.embed import Embedder, EmbeddingError
from app.rag.models import AskRequest, Passage
from app.rag.search import RetrievedPassage, search
from app.settings import get_settings
from app.telemetry.ai import ai_call, record_refusal

logger = logging.getLogger(__name__)

LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
SOURCES = "the Income Tax Ordinance and FBR's return-filing manual"
NOT_COVERED_MESSAGE = f"I can only answer from {SOURCES}, and they don't cover this."
LIMITED_MESSAGE = "You've asked a lot of questions in the past hour. Please try again later."
DAILY_LIMIT_MESSAGE = "The tax assistant has reached today's limit; try again tomorrow."
UNAVAILABLE_MESSAGE = "The tax assistant couldn't answer just now. Please try again later."
NOT_READY_MESSAGE = "The tax assistant isn't ready yet."
# Written by code, never by the AI (FR-007).
TAX_PAGE_LINE = "To see your own calculated tax, open the Tax page."

HOURLY_LIMIT = 30  # per user (FR-009a)
# SC-004 (amended): an answer or a refusal within 15 seconds, embedding and answer together.
ASK_SECONDS = 15.0
_KEEP = timedelta(days=1)

Status = Literal["answered", "not_covered", "limited", "daily_limit", "unavailable", "not_ready"]


class Answerer(Protocol):  # pylint: disable=too-few-public-methods
    """Writes an answer from the passages found."""

    async def answer(self, question: str, passages: Sequence[RetrievedPassage]) -> ModelAnswer:
        """The model's structured answer, or an AnswerError."""
        ...  # pylint: disable=unnecessary-ellipsis


@dataclass(frozen=True)
class Citation:
    """What a reader needs to find the passage: document, law or guidance, location, page."""

    title: str
    kind: str
    location: str
    page: int


@dataclass(frozen=True)
class AskResult:
    """The response to one question (contracts/ask-and-tokens-api.md)."""

    status: Status
    answer: str
    citations: list[Citation] = field(default_factory=list)
    uncovered_part: str | None = None
    tax_page_line: str | None = None
    label: str = LABEL


_REFUSALS: dict[Status, str] = {
    "not_covered": NOT_COVERED_MESSAGE,
    "limited": LIMITED_MESSAGE,
    "daily_limit": DAILY_LIMIT_MESSAGE,
    "unavailable": UNAVAILABLE_MESSAGE,
    "not_ready": NOT_READY_MESSAGE,
}


def refusal_message(status: Status) -> str:
    """The fixed message for a refusal (also used by the MCP server's search)."""
    return _REFUSALS[status]


def _refusal(status: Status) -> AskResult:
    return AskResult(status=status, answer=_REFUSALS[status])


async def ask(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    embedder: Embedder,
    answerer: Answerer,
) -> AskResult:
    """Answer one question from the corpus, or say why not."""
    if not (await db.execute(select(exists().where(Passage.id.is_not(None))))).scalar_one():
        return _refusal("not_ready")
    if not written_in_english(question):
        # Out of scope (English questions only): refused before it counts or reaches any AI.
        return _refusal("not_covered")
    refused = await use_question(db, user_id)
    # Committed either way: the question counts even if what follows fails, old records stay
    # deleted, and the app-wide lock is released before the slow part.
    await db.commit()
    if refused is not None:
        record_refusal("assistant", get_settings().answer_model)
        return _refusal(refused)
    return (await answer_question(db, question, embedder, answerer)).result


@dataclass(frozen=True)
class Outcome:
    """A question's result and the step that decided it (for the answers eval)."""

    result: AskResult
    step: str  # answered, or refused: not English / cut-off / model / checks, or unavailable
    detail: str = ""


async def answer_question(
    db: AsyncSession, question: str, embedder: Embedder, answerer: Answerer
) -> Outcome:
    """Search, answer and check one question, all within ASK_SECONDS; not counted here (ask()
    counts it first). A failure or timeout is "unavailable"."""
    try:
        return await asyncio.wait_for(_answer(db, question, embedder, answerer), ASK_SECONDS)
    except (EmbeddingError, AnswerError, TimeoutError) as exc:
        # Error types only (e.g. AnswerError from ServerError, Gemini's 503 "high demand"): an
        # error's text could hold the question, which is never kept (FR-009).
        cause = exc.__cause__
        logger.warning(
            "Ask unavailable: %s%s",
            type(exc).__name__,
            f" from {type(cause).__name__}" if cause is not None else "",
        )
        return Outcome(_refusal("unavailable"), "unavailable", type(exc).__name__)


async def _answer(
    db: AsyncSession, question: str, embedder: Embedder, answerer: Answerer
) -> Outcome:
    if not written_in_english(question):
        return Outcome(_refusal("not_covered"), "refused: not English")
    found = await search(db, embedder, question)
    # End the read transaction now, so no connection waits idle in it during the AI call.
    await db.commit()
    if not found.covered:
        top = found.passages[0].score if found.passages else 0.0
        return Outcome(_refusal("not_covered"), "refused: cut-off", f"top score {top:.3f}")
    with ai_call("assistant", get_settings().answer_model) as call:
        reply = await answerer.answer(question, found.passages)
        cited = None if reply.not_covered else checked_citations(reply, found.passages)
        if not reply.not_covered and cited is None:
            call.outcome = "check_failed"
    # Still pointed to the Tax page when they asked for their own figure (FR-007).
    tax_page_line = TAX_PAGE_LINE if reply.asks_own_tax_figure else None
    not_covered = AskResult(
        status="not_covered", answer=NOT_COVERED_MESSAGE, tax_page_line=tax_page_line
    )
    if reply.not_covered:
        return Outcome(not_covered, "refused: model")
    if cited is None:
        return Outcome(not_covered, "refused: checks", f"{reply.citations}: {reply.answer}")
    answered = AskResult(
        status="answered",
        answer=reply.answer,
        citations=[Citation(p.title, p.kind.value, p.location, p.page) for p in cited],
        uncovered_part=reply.uncovered_part,
        tax_page_line=tax_page_line,
    )
    return Outcome(answered, "answered", f"{', '.join(p.location for p in cited)}: {reply.answer}")


async def use_question(db: AsyncSession, user_id: uuid.UUID) -> Status | None:
    """Count one question (an Ask question or an MCP search), or say which limit refuses it.

    One app-wide lock (held until the transaction ends) stops questions sent together from all
    reading the counts before any is recorded, as 003's use_extraction does. Records older than
    a day, which no limit needs, are deleted here.
    """
    await db.execute(
        sql_text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": "ask-requests"},
    )
    now = datetime.now(UTC)
    await db.execute(delete(AskRequest).where(AskRequest.created_at <= now - _KEEP))
    count = select(func.count()).select_from(AskRequest)
    if (
        await db.execute(count.where(AskRequest.created_at > now - _KEEP))
    ).scalar_one() >= get_settings().ask_daily_limit:
        return "daily_limit"
    mine = count.where(
        AskRequest.user_id == user_id, AskRequest.created_at > now - timedelta(hours=1)
    )
    if (await db.execute(mine)).scalar_one() >= HOURLY_LIMIT:
        return "limited"
    db.add(AskRequest(user_id=user_id, created_at=now))
    await db.flush()
    return None
