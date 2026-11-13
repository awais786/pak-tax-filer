"""A short plain-language summary of the reconciliation, checked before use (feature 005, T016).

The same pattern as the tax page (004): Gemini writes 2-3 sentences from the breakdown, then the
shared plain-code check (app.explain.number_check) drops it if any number isn't in the
breakdown or is written as a word (FR-010, constitution Principle I). It has 4 seconds; late,
failed or refused means no summary, and the breakdown never waits on it. The "where to look"
checklist is code-written only, so it is never shown to the model to rephrase (FR-007).
"""

import asyncio
import logging
import re

from app.explain.number_check import numbers_in, uses_only_numbers_from
from app.settings import get_settings
from app.tax.summary import LIMIT_SECONDS, Summariser
from app.telemetry.ai import ai_call
from app.wealth.reconcile import ReconciliationResult

logger = logging.getLogger(__name__)

WEALTH_INSTRUCTIONS = """\
You explain a wealth reconciliation to the taxpayer in 2 or 3 short, plain sentences. Use only \
the numbers that appear in the breakdown you are given, written the same way (e.g. \
"Rs 50,000"). Do not calculate, round or add any new number, never write numbers as words (no \
"lakh", "million", "thousand"), and never suggest an amount to enter. Do not give advice."""


# Backend reviews H1 (two passes): the amount that would force a zero is always in the
# breakdown, so the number check alone can't stop a summary suggesting it. Plain-code checks,
# sentence by sentence, drop a summary that advises, ties the gap amount to something to add,
# claims a reconciliation that isn't there, or states the other direction. Harmless wording
# ("reconciliation", "unreconciled", "inflows exceed outflows") is left alone.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# Telling the user what to do, anywhere.
_ADVICE = re.compile(r"\b(?:should|must|need to|have to|ought to)\b", re.IGNORECASE)
# Words that, beside the gap amount, would point the user at what to enter (stems on purpose:
# "adding", "entered", "listing"...), and the checklist's own categories (FR-007).
_SUGGESTION = re.compile(
    # Not "assets", "shows" or "may be missing": the app's own message ("Your assets grew Rs X
    # more than your inflows explain: an inflow may be missing") must stay allowed.
    r"\b(?:enter|add|declar|includ|put|record|list|report|consider|claim|clear|clos|fix|"
    r"remov|bring|gift|inherit|remittance|family|exempt|vehicle|jewel|savings|bank account)\w*",
    re.IGNORECASE,
)
# "reconciles", "reconciled", "balance(d)" - not "reconciliation" or "unreconciled".
_RECONCILED = re.compile(r"\b(?:reconciles|reconciled|balanc\w*)\b", re.IGNORECASE)
_GROWTH_WORD = r"(?:grew|grow\w*|increase\w*|rose|risen)"
_MORE = r"(?:exceed\w*|more than|greater than|larger than|above)"
# Inflows are more than the growth (inflows_exceed_growth).
_INFLOWS_OVER = re.compile(
    rf"\binflows?\b[^.]*\b{_MORE}[^.]*\b{_GROWTH_WORD}", re.IGNORECASE | re.DOTALL
)
# The growth is more than the inflows, or inflows fall short (growth_exceeds_inflows).
_GROWTH_OVER = re.compile(
    rf"\b{_GROWTH_WORD}\b[^.]*\b{_MORE}[^.]*\binflows?\b|\binflows?\b[^.]*\bshort\b",
    re.IGNORECASE | re.DOTALL,
)


def wealth_summary_is_safe(summary: str, result: ReconciliationResult) -> bool:
    """False if the summary gives advice or says something other than the result."""
    if _ADVICE.search(summary):
        return False
    direction = result.direction
    if _RECONCILED.search(summary) and direction != "reconciled":
        return False
    if _INFLOWS_OVER.search(summary) and direction != "inflows_exceed_growth":
        return False
    if _GROWTH_OVER.search(summary) and direction != "growth_exceeds_inflows":
        return False
    gap = abs(result.unreconciled) if result.unreconciled else None
    for sentence in _SENTENCE_END.split(summary):
        if gap is not None and gap in numbers_in(sentence) and _SUGGESTION.search(sentence):
            return False
    return True


def wealth_breakdown_text(result: ReconciliationResult, tax_year: str) -> str:
    """What the model sees: the tax year, each step and the result in words."""
    lines = [f"Wealth statement for tax year {tax_year}."]
    lines += [f"- {step.description}" for step in result.steps]
    lines.append(f"Result: {result.message}")
    return "\n".join(lines)


async def verified_wealth_summary(
    result: ReconciliationResult,
    tax_year: str,
    summariser: Summariser,
    limit_seconds: float = LIMIT_SECONDS,
) -> str | None:
    """The summary if it arrives in time and uses only the breakdown's numbers; else None."""
    if result.not_ready_reason is not None or not result.steps:
        return None
    source = wealth_breakdown_text(result, tax_year)
    with ai_call("wealth_summary", get_settings().summary_model) as call:
        try:
            text = await asyncio.wait_for(summariser.write(source), limit_seconds)
        except TimeoutError:
            call.outcome = "timeout"
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # optional; never breaks the result
            logger.warning("Wealth summary failed")
            call.outcome = "fallback"
            return None
        if text is None:
            call.outcome = "fallback"
            return None
        if not uses_only_numbers_from(text, source) or not wealth_summary_is_safe(text, result):
            call.outcome = "check_failed"
            return None
        return text.strip()
