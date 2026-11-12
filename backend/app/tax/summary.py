"""A short plain-language summary of the breakdown, checked before use (feature 004, T018; R8).

Gemini writes 2-3 sentences from the breakdown. Then plain code checks every number in them: any
number not in the breakdown, or any number word ("lakh", "1.8 million"), and the summary is
dropped (constitution Principle I, FR-011). It has its own request (GET .../summary), so the
figures never wait on it (feature 001, User Story 6); late, refused or failed means no summary.
No tax figure is produced here.
"""

import asyncio
import logging
import re
from decimal import Decimal
from typing import Protocol

import httpx2
from google import genai
from google.genai import errors, types

from app.documents.extraction.client import THINKING_LEVELS
from app.explain.number_check import numbers_in, uses_only_numbers_from
from app.settings import get_settings
from app.tax.engine import TaxResult, rupees
from app.telemetry.ai import ai_call, record_gemini_usage

logger = logging.getLogger(__name__)

# The summary is loaded after the figures, so it can take longer than the 4 s it once had while
# the page waited (from Pakistan Gemini often needed more, and the summary was always dropped).
LIMIT_SECONDS = 12.0
# The deadline sent to Google (Gemini refuses anything under 10 s, 400 INVALID_ARGUMENT); the
# limit above is a little longer, so Google's own timeout is the one normally seen.
GOOGLE_DEADLINE_MS = 10_000
INSTRUCTIONS = """\
You explain an income tax result to the taxpayer in 2 or 3 short, plain sentences. Use only the \
numbers that appear in the breakdown you are given, written the same way (e.g. "Rs 72,000"). Do \
not calculate, round or add any new number, and never write numbers as words (no "lakh", \
"million", "thousand"). Do not give advice. The salary tax and the tax on bank profit are worked \
out before anything is taken off; the tax deducted by employers and the tax withheld by banks are \
then subtracted from them. Never describe a tax figure as being after, net of or accounting for \
tax deducted or withheld."""

# The balance's direction, in the words a summary might use. "Refund" is never allowed: the app
# never promises one (FR-013), and an over-deduction isn't a refund until FBR says so.
_PAYABLE_WORDS = re.compile(r"\b(?:owe|owes|owed|owing|payable|outstanding)\b", re.IGNORECASE)
_OVERPAID_WORDS = re.compile(
    r"\b(?:over-?deducted|over-?withheld|overpaid|excess)\b", re.IGNORECASE
)
_REFUND = re.compile(r"\brefund", re.IGNORECASE)

# Feature 001, User Story 6: a live summary said "salary tax Rs 1,666,193 after accounting for
# Rs 213,016 deducted", every number right, the relation wrong (the tax is before the
# deduction). Checked sentence by sentence, as the wealth summary's guards are: a sentence with
# a tax figure, its credit and wording like this, that never reaches the balance, is dropped.
# "After subtracting Rs 213,016 ... Rs 1,453,177 payable" reaches the balance, so it is kept.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_NET_OF = re.compile(
    r"\b(?:after|net of|accounting for|taking into account|inclusive of|including|less|minus)\b",
    re.IGNORECASE,
)


def _names(numbers: set[Decimal], amount: Decimal | None) -> bool:
    """True if the sentence writes this amount, exactly or before its s.219 rounding."""
    return amount is not None and any(rupees(n) == abs(amount) for n in numbers)


def _deduction_inside_the_tax(summary: str, result: TaxResult) -> bool:
    sides = [
        (result.salary_tax, result.salary_credit, result.salary_balance),
        (result.profit_tax, result.profit_credit, result.profit_balance),
    ]
    for sentence in _SENTENCE_END.split(summary):
        if not _NET_OF.search(sentence):
            continue
        numbers = numbers_in(sentence)
        for tax, credit, balance in sides:
            if not credit:  # nothing was taken off, so no relation to get wrong
                continue
            if _names(numbers, tax) and _names(numbers, credit) and not _names(numbers, balance):
                return True
    return False


def breakdown_text(result: TaxResult) -> str:
    """The breakdown as the model sees it: the tax year and each step."""
    lines = [f"Tax year {result.tax_year}."] + [f"- {step.description}" for step in result.steps]
    return "\n".join(lines)


def summary_is_safe(summary: str, result: TaxResult) -> bool:
    """True only if every number in the summary appears in the breakdown, none is a word, and
    it doesn't reverse a balance (payable vs over-deducted) or mention a refund.

    Known limit (research R8): a right number can still be attached to the wrong figure
    ("your tax is Rs 600,000"); the breakdown beside it is the authoritative answer."""
    if _REFUND.search(summary) or _deduction_inside_the_tax(summary, result):
        return False
    balances = [b for b in (result.salary_balance, result.profit_balance) if b is not None]
    if _PAYABLE_WORDS.search(summary) and not any(b > 0 for b in balances):
        return False
    if _OVERPAID_WORDS.search(summary) and not any(b < 0 for b in balances):
        return False
    return uses_only_numbers_from(summary, breakdown_text(result))


class Summariser(Protocol):  # pylint: disable=too-few-public-methods
    """Writes a short summary from the breakdown text, or None."""

    async def write(self, breakdown: str) -> str | None:
        """The model's summary, or None."""


class GeminiSummariser:  # pylint: disable=too-few-public-methods
    """Writes the summary with Gemini (free tier); any failure is None, never an error."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        http_client: httpx2.AsyncClient | None = None,
        instructions: str = INSTRUCTIONS,
    ) -> None:
        self._api_key = api_key
        # The tax page's by default; the wealth page (005) passes its own.
        self._instructions = instructions
        self._model = model
        self._effort = effort
        self._http_client = http_client

    async def write(self, breakdown: str) -> str | None:
        """Ask Gemini for 2-3 sentences; no retries (the 4-second budget doesn't allow them)."""
        if not self._api_key:
            return None
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                httpx_async_client=self._http_client,
            ),
        )
        try:
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=breakdown,
                config=types.GenerateContentConfig(
                    system_instruction=self._instructions,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=THINKING_LEVELS[self._effort]
                    ),
                    max_output_tokens=300,
                    http_options=types.HttpOptions(timeout=GOOGLE_DEADLINE_MS),
                ),
            )
        except (errors.APIError, httpx2.HTTPError) as exc:
            logger.warning("Summary failed: %s", type(exc).__name__)
            return None
        record_gemini_usage(response.usage_metadata)
        candidates = response.candidates or []
        if not candidates or candidates[0].finish_reason != types.FinishReason.STOP:
            # Cut short (e.g. MAX_TOKENS) or blocked: a fragment like "For tax year 2025" passes
            # the number check, so it must never be used (004 quickstart 2.2, 2026-11-10).
            return None
        return response.text or None


class FakeSummariser:  # pylint: disable=too-few-public-methods
    """Returns a fixed answer (tests): text, an error to raise, and a delay in seconds."""

    def __init__(
        self, text: str | None = None, *, error: Exception | None = None, delay: float = 0
    ) -> None:
        self.text = text
        self.error = error
        self.delay = delay

    async def write(self, breakdown: str) -> str | None:
        """The fixed answer, after the delay."""
        del breakdown
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.text


async def verified_summary(
    result: TaxResult, summariser: Summariser, limit_seconds: float = LIMIT_SECONDS
) -> str | None:
    """The summary if it arrives in time and passes the number check; otherwise None."""
    if result.blocked_reason is not None or not result.steps:
        return None
    with ai_call("tax_summary", get_settings().summary_model) as call:
        try:
            text = await asyncio.wait_for(summariser.write(breakdown_text(result)), limit_seconds)
        except TimeoutError:
            call.outcome = "timeout"
            return None
        except Exception:  # pylint: disable=broad-exception-caught  # optional; must never break the result
            logger.warning("Summary failed")
            call.outcome = "fallback"
            return None
        if text is None:
            call.outcome = "fallback"
            return None
        if not summary_is_safe(text, result):
            call.outcome = "check_failed"
            return None
        return text.strip()
