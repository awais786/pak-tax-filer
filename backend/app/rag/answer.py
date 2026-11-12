"""Writing an answer from the passages found (feature 006, task T011; research R5 amended).

Gemini answers only from the retrieved passages, labelled P1..P5, and returns structured
output: the answer, the labels it relied on, whether the passages don't cover the question, any
part they don't cover, and whether the question asks for the user's own tax figure. Plain code
then checks all of it before anything is shown (checks.py); the model never writes the
not-covered message or the Tax page line, and never produces a tax figure (Principle I).
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx2
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.documents.extraction.client import THINKING_LEVELS
from app.rag.search import RetrievedPassage
from app.telemetry.ai import record_gemini_usage

logger = logging.getLogger(__name__)

# Google's own deadline (Gemini refuses under 10 s); the service waits at most 15 s in all.
GOOGLE_DEADLINE_MS = 14_000
# Gemini's 503 "high demand" (2 of 10 real questions on 2026-11-11) comes back in about 2 s, so
# one more try, a second later, still fits the 15 s; nothing else is retried.
RETRY = types.HttpRetryOptions(
    attempts=2, initial_delay=1.0, max_delay=1.0, http_status_codes=[503]
)

INSTRUCTIONS = """\
You answer a question from a salaried taxpayer in Pakistan, using ONLY the numbered passages you \
are given from FBR's texts (the Income Tax Ordinance and FBR's return-filing manual).
- Answer in 2 to 5 short, plain sentences. Do not give advice or opinions.
- List in "citations" the label (P1, P2, ...) of every passage you relied on. Never write the \
labels in the answer text itself.
- Quote figures, rates and section numbers exactly as the passages write them. Never calculate, \
round or add a number, and never write numbers as words ("lakh", "million").
- If the passages don't answer the question, set "not_covered" to true and leave "answer" empty.
- If they answer only part of it, answer that part and say briefly in "uncovered_part" what \
isn't covered, without any numbers.
- If the question asks for the user's own tax amount or refund, set "asks_own_tax_figure" to \
true and give no figure; you may still explain the rule from the passages."""


@dataclass(frozen=True)
class ModelAnswer:
    """The model's structured reply, before any check."""

    answer: str
    citations: list[str]
    not_covered: bool
    uncovered_part: str | None
    asks_own_tax_figure: bool


class AnswerError(Exception):
    """The model couldn't answer (API error, refusal, cut short or an unreadable reply)."""


class _Reply(BaseModel):
    """The JSON shape Gemini must return."""

    answer: str
    citations: list[str]
    not_covered: bool
    uncovered_part: str | None
    asks_own_tax_figure: bool


def prompt(question: str, passages: Sequence[RetrievedPassage]) -> str:
    """The question and the passages, each with its label and citation."""
    lines = [f"Question: {question}", "", "Passages:"]
    for number, passage in enumerate(passages, 1):
        lines.append(
            f"[P{number}] {passage.title}, {passage.location} ({passage.kind.value}, "
            f"page {passage.page}):"
        )
        lines.append(passage.text)
        lines.append("")
    return "\n".join(lines)


class GeminiAnswerer:  # pylint: disable=too-few-public-methods
    """Answers with Gemini (free tier); any failure is an AnswerError."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._effort = effort
        self._http_client = http_client

    async def answer(self, question: str, passages: Sequence[RetrievedPassage]) -> ModelAnswer:
        """The model's answer from these passages only."""
        if not self._api_key:
            raise AnswerError("No GEMINI_API_KEY is set.")
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                retry_options=RETRY,
                httpx_async_client=self._http_client,
            ),
        )
        try:
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=prompt(question, passages),
                config=types.GenerateContentConfig(
                    system_instruction=INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_schema=_Reply,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=THINKING_LEVELS[self._effort]
                    ),
                    max_output_tokens=800,
                    http_options=types.HttpOptions(timeout=GOOGLE_DEADLINE_MS),
                ),
            )
        except (errors.APIError, httpx2.HTTPError) as exc:
            raise AnswerError(type(exc).__name__) from exc
        record_gemini_usage(response.usage_metadata)
        candidates = response.candidates or []
        if not candidates or candidates[0].finish_reason != types.FinishReason.STOP:
            # Cut short or blocked: a partial JSON answer must never be used.
            raise AnswerError("The answer was cut short or blocked.")
        try:
            reply = _Reply.model_validate(json.loads(response.text or ""))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AnswerError("The answer wasn't in the expected form.") from exc
        return ModelAnswer(
            answer=reply.answer.strip(),
            citations=reply.citations,
            not_covered=reply.not_covered,
            uncovered_part=(reply.uncovered_part or "").strip() or None,
            asks_own_tax_figure=reply.asks_own_tax_figure,
        )


@dataclass
class FakeAnswerer:
    """A fixed reply for tests (or an exception to raise), recording what it was asked."""

    reply: ModelAnswer | BaseException
    calls: list[tuple[str, list[RetrievedPassage]]] = field(default_factory=list)

    async def answer(self, question: str, passages: Sequence[RetrievedPassage]) -> ModelAnswer:
        """Record the call; return the reply or raise it."""
        self.calls.append((question, list(passages)))
        if isinstance(self.reply, BaseException):
            raise self.reply
        return self.reply
