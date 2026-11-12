"""The document, validation and research agents (feature 007, task T009; research R4, R5).

Plain code decides each step's facts: what's missing, which of 003's rules break, which corpus
passages exist. An agent only explains them, with its own read-only tools, in 15 seconds at
most. Its text is shown only if it passes the checks: 004's number check for the document and
validation steps, 006's citation and number checks for research. Otherwise, and whenever the AI
is unavailable, slow or not allowed (a question limit), the step shows its plain result, marked
`fallback: true`. No agent can confirm, edit, approve or calculate anything (Principle III).
"""

import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument
from app.explain.number_check import uses_only_numbers_from
from app.rag.answer import ModelAnswer
from app.rag.checks import checked_citations
from app.rag.embed import EmbeddingError
from app.rag.search import RetrievedPassage, search
from app.settings import get_settings
from app.telemetry.ai import AiCall, ai_call, record_refusal
from app.workflow.client import AgentClient, AgentError
from app.workflow.settings import STEP_SECONDS
from app.workflow.tools import AGENT_TOOLS, UPLOAD_PAGE, Toolbox

Reply = TypeVar("Reply", bound=BaseModel)
logger = logging.getLogger(__name__)

COMMON = (
    "You help a salaried taxpayer in Pakistan through a guided tax return. Write 1 to 3 short, "
    "plain sentences. Never give a tax amount, never calculate, round or add a number, and never "
    "write numbers as words. You can't confirm, change or approve anything: say what the user "
    "should do."
)
DOCUMENT_INSTRUCTIONS = (
    f"{COMMON} Call list_confirmed_documents, then say which certificates are confirmed and "
    "what's missing: a confirmed salary certificate is required; a bank profit certificate is "
    "optional. Tell the user to upload and confirm missing certificates on the Documents page."
)
VALIDATION_INSTRUCTIONS = (
    f"{COMMON} Call validate_salary_information or check_bank_certificate for every certificate "
    "given, all in your first turn (one call per certificate, together), with its figures exactly "
    "as given. Then explain any issue found, naming the certificate to fix; if there is none, say "
    "the figures are consistent."
)
RESEARCH_INSTRUCTIONS = (
    f"{COMMON} Search the FBR texts (search_tax_documents, at most 3 searches) for the law that "
    "applies to the income given: first how the Income Tax Ordinance taxes it and who deducts "
    "tax from it (for salary, e.g. 'how is my salary taxed' and 'does my employer deduct tax'), "
    "then, if useful, the return-filing manual on where to enter it. Then write a short note on "
    "which passages apply and why, citing the Ordinance's sections first, and "
    "list in citations the labels (P1, P2, ...) of the passages you relied on. Quote section "
    "numbers and figures only as the passages write them."
)

# Fixed searches for the plain research result, per income type (worded as users ask, so they
# clear the relevance cut-off).
_PLAIN_QUERIES = {
    DocType.SALARY_CERTIFICATE: (
        "Is my monthly salary counted as taxable income?",
        "How does my company work out how much tax to take from each paycheck?",
    ),
    DocType.BANK_PROFIT_CERTIFICATE: ("Does my bank keep some of my savings profit as tax?",),
}
_PLAIN_PER_QUERY = 2


class _Message(BaseModel):
    message: str


class _Note(BaseModel):
    note: str
    citations: list[str]


async def _ask(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: AgentClient,
    agent: str,
    instructions: str,
    prompt: str,
    tools: Toolbox,
    reply: type[Reply],
    call: AiCall,
) -> Reply | None:
    """The agent's answer within the step's time, or None if it failed or was too slow (and
    `call` says which)."""
    try:
        return await asyncio.wait_for(
            client.run(agent, instructions, prompt, tools, AGENT_TOOLS[agent], reply), STEP_SECONDS
        )
    except TimeoutError:
        call.outcome = "timeout"
        return None
    except (AgentError, EmbeddingError):
        call.outcome = "fallback"
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Any other failure (a bad tool argument, the SDK, the database) also gives the plain
        # result rather than a half-finished run (backend review M2). The type only is logged.
        logger.warning("Workflow agent %s failed: %s", agent, type(exc).__name__)
        call.outcome = "fallback"
        return None


def _model() -> str:
    return get_settings().workflow_model


# ---- Document step (FR-003) ----


async def document_step(client: AgentClient, tools: Toolbox, *, use_ai: bool) -> dict[str, Any]:
    """What's confirmed and what's missing; a confirmed salary certificate is required."""
    listed = await tools.list_confirmed_documents()
    types = {c["type"] for c in listed["certificates"]}
    missing = [] if DocType.SALARY_CERTIFICATE.value in types else ["salary_certificate"]
    # Only what the message may mention: the labels and what's missing, not ids or timestamps,
    # whose digits would otherwise count as allowed numbers (backend review L5).
    source = json.dumps(
        {"labels": [c["label"] for c in listed["certificates"]], "missing": missing}
    )
    if not use_ai:
        record_refusal("workflow_document", _model())
    else:
        with ai_call("workflow_document", _model()) as call:
            answer = await _ask(
                client,
                "document",
                DOCUMENT_INSTRUCTIONS,
                f"Missing: {missing}",
                tools,
                _Message,
                call,
            )
            if answer and answer.message.strip() and uses_only_numbers_from(answer.message, source):
                return {"message": answer.message.strip(), "missing": missing, "fallback": False}
            if answer is not None:
                call.outcome = "check_failed"
    return {"message": _plain_document(listed, missing), "missing": missing, "fallback": True}


def _plain_document(listed: dict[str, Any], missing: list[str]) -> str:
    confirmed = ", ".join(c["label"] for c in listed["certificates"]) or "none yet"
    if missing:
        return (
            f"Confirmed certificates: {confirmed}. You need at least one confirmed salary "
            "certificate: upload and confirm it on the Documents page "
            f"({UPLOAD_PAGE}). A bank profit certificate is optional."
        )
    return (
        f"Confirmed certificates: {confirmed}. A bank profit certificate is optional; add one on "
        "the Documents page if you have one."
    )


# ---- Validation step (FR-004) ----


async def validation_step(
    client: AgentClient,
    tools: Toolbox,
    documents: Sequence[ConfirmedDocument],
    *,
    use_ai: bool,
) -> dict[str, Any]:
    """003's rule checks on every confirmed certificate, explained; issues warn, never block."""
    certificates = [_certificate(d) for d in documents]
    issues = []
    for certificate in certificates:
        check = await _check(tools, certificate)
        issues += [
            {
                "document_id": certificate["id"],
                "certificate": certificate["label"],
                "field": issue["field"],
                "reason": issue["reason"],
            }
            for issue in check["issues"]
        ]
    source = json.dumps({"certificates": certificates, "issues": issues})
    if certificates and not use_ai:
        record_refusal("workflow_validation", _model())
    elif certificates:
        prompt = f"Certificates: {json.dumps(certificates)}"
        with ai_call("workflow_validation", _model()) as call:
            answer = await _ask(
                client, "validation", VALIDATION_INSTRUCTIONS, prompt, tools, _Message, call
            )
            if answer and answer.message.strip() and uses_only_numbers_from(answer.message, source):
                return {"message": answer.message.strip(), "issues": issues, "fallback": False}
            if answer is not None:
                call.outcome = "check_failed"
    return {"message": _plain_validation(issues), "issues": issues, "fallback": True}


def _certificate(document: ConfirmedDocument) -> dict[str, Any]:
    label = (
        "Salary certificate"
        if document.doc_type is DocType.SALARY_CERTIFICATE
        else "Bank certificate"
    )
    if document.uploaded_at:
        label = f"{label} uploaded {document.uploaded_at:%d %b %Y}"
    return {
        "id": str(document.id),
        "type": document.doc_type.value,
        "label": label,
        "figures": {name.value: str(value) for name, value in document.values.items()},
    }


async def _check(tools: Toolbox, certificate: dict[str, Any]) -> dict[str, Any]:
    figures = certificate["figures"]
    year = figures.get(FieldName.TAX_YEAR.value, "")
    if certificate["type"] == DocType.SALARY_CERTIFICATE.value:
        return await tools.validate_salary_information(
            year,
            figures.get("gross_salary", ""),
            figures.get("taxable_salary", ""),
            figures.get("tax_deducted", ""),
        )
    return await tools.check_bank_certificate(
        year, figures.get("profit_amount", ""), figures.get("tax_withheld", "")
    )


def _plain_validation(issues: list[dict[str, str]]) -> str:
    if not issues:
        return "The figures on your confirmed certificates are consistent."
    lines = "; ".join(f"{i['certificate']}: {i['reason']}" for i in issues)
    return f"Please check these before you approve: {lines}"


# ---- Research step (FR-005) ----


async def research_step(
    client: AgentClient,
    tools: Toolbox,
    documents: Sequence[ConfirmedDocument],
    *,
    use_ai: bool,
) -> dict[str, Any]:
    """The tax-law passages that apply, each with its citation, from 006's corpus only."""
    income = sorted({d.doc_type.value for d in documents}) or ["salary_certificate"]
    if not use_ai:
        record_refusal("workflow_research", _model())
    else:
        prompt = f"The user's income comes from: {', '.join(income)}."
        with ai_call("workflow_research", _model()) as call:
            answer = await _ask(
                client, "research", RESEARCH_INSTRUCTIONS, prompt, tools, _Note, call
            )
            cited = _checked_note(answer, tools.found)
            if answer and cited:
                return {
                    "note": answer.note.strip(),
                    "passages": _passages(cited),
                    "fallback": False,
                }
            if answer is not None:
                call.outcome = "check_failed"
    return await _plain_research(tools, [DocType(i) for i in income])


def _checked_note(
    answer: _Note | None, found: list[RetrievedPassage]
) -> list[RetrievedPassage] | None:
    """The cited passages if the note passes 006's checks (citations among the passages search
    returned; every number, with its scale, in a cited passage), else None."""
    if answer is None:
        return None
    reply = ModelAnswer(
        answer=answer.note,
        citations=answer.citations,
        not_covered=False,
        uncovered_part=None,
        asks_own_tax_figure=False,
    )
    return checked_citations(reply, found)


async def _plain_research(tools: Toolbox, income: list[DocType]) -> dict[str, Any]:
    passages: list[RetrievedPassage] = []
    for doc_type in income:
        for query in _PLAIN_QUERIES[doc_type]:
            try:
                result = await asyncio.wait_for(_search(tools, query), STEP_SECONDS)
            except (EmbeddingError, TimeoutError):
                continue
            for passage in result[:_PLAIN_PER_QUERY]:
                if passage.id not in {p.id for p in passages}:
                    passages.append(passage)
    if not passages:
        return {
            "note": "No passages found in the FBR texts for your income.",
            "passages": [],
            "fallback": True,
        }
    return {
        "note": "These passages from the FBR texts apply to your income.",
        "passages": _passages(passages),
        "fallback": True,
    }


async def _search(tools: Toolbox, query: str) -> list[RetrievedPassage]:
    async with tools.sessions() as db:
        result = await search(db, tools.embedder, query)
    return list(result.passages) if result.covered else []


def _passages(passages: Sequence[RetrievedPassage]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(p.id),
            "source": p.title,
            "kind": p.kind.value,
            "location": p.location,
            "page": p.page,
            "text": p.text,
        }
        for p in passages
    ]
