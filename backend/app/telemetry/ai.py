"""AI-use spans (feature 008, task T019; research R3, FR-011).

Every use of Gemini is one span, opened where the app decides how the use ended: `ai_call` around
the call and the checks on its answer, or `record_refusal` when a limit stopped it before any
call. The real clients add their token counts to the current span with `record_usage`; an
agent's tool calls are child spans from `tool_call`. OpenTelemetry's GenAI attribute names are
still "Development", so they live only here.

Only these attributes are set: never a prompt, a reply, a figure or anything about the user.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind

Feature = Literal[
    "extraction",
    "tax_summary",
    "wealth_summary",
    "assistant",
    "embeddings",
    "workflow_document",
    "workflow_validation",
    "workflow_research",
]
Outcome = Literal["passed", "check_failed", "timeout", "fallback", "limit_reached"]
Operation = Literal["generate_content", "embeddings"]

PROVIDER = "gcp.gemini"  # Gemini through the AI Studio endpoint
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

_tracer = trace.get_tracer(__name__)
# The AI use a tool call belongs to (an agent's feature).
_current: ContextVar[str | None] = ContextVar("ai_feature", default=None)


@dataclass
class AiCall:
    """How one AI use ended: "passed" unless the caller says otherwise or an error escapes."""

    outcome: Outcome = "passed"


@contextmanager
def ai_call(
    feature: Feature, model: str, operation: Operation = "generate_content"
) -> Iterator[AiCall]:
    """A span for one AI use. Set `outcome` on what it yields; an escaping timeout or
    cancellation is "timeout", any other error "fallback" (the error itself is not recorded)."""
    with _tracer.start_as_current_span(
        f"{operation} {model}",
        kind=SpanKind.CLIENT,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attributes(
            {
                "gen_ai.provider.name": PROVIDER,
                "gen_ai.operation.name": operation,
                "gen_ai.request.model": model,
                "app.feature": feature,
            }
        )
        call = AiCall()
        token = _current.set(feature)
        try:
            yield call
        except (TimeoutError, asyncio.CancelledError):
            call.outcome = "timeout"
            raise
        except BaseException:  # any other error, or the coroutine closed or interrupted
            call.outcome = "fallback"
            raise
        finally:
            try:
                _current.reset(token)
            except ValueError:  # a coroutine closed from another context (garbage collection)
                pass
            span.set_attribute("app.outcome", call.outcome)


def record_refusal(feature: Feature, model: str, operation: Operation = "generate_content") -> None:
    """An AI use a limit stopped before any call (outcome "limit_reached")."""
    with ai_call(feature, model, operation) as call:
        call.outcome = "limit_reached"


@contextmanager
def tool_call(name: str) -> Iterator[None]:
    """A span for one tool an agent called (`execute_tool`), under the agent's AI use."""
    with _tracer.start_as_current_span(
        f"execute_tool {name}",
        kind=SpanKind.INTERNAL,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        attributes = {
            "gen_ai.provider.name": PROVIDER,
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": name,
        }
        feature = _current.get()
        if feature is not None:
            attributes["app.feature"] = feature
        span.set_attributes(attributes)
        yield


def record_usage(input_tokens: int | None, output_tokens: int | None) -> None:
    """Add a reply's token counts to the current AI span (an agent's turns add up)."""
    span = trace.get_current_span()
    if not span.is_recording():
        return
    _add(span, INPUT_TOKENS, input_tokens)
    _add(span, OUTPUT_TOKENS, output_tokens)


def record_gemini_usage(usage: Any) -> None:
    """Token counts from a Gemini reply's `usage_metadata` (output includes the thinking)."""
    if usage is None:
        return
    output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    record_usage(usage.prompt_token_count, output if output else None)


def _add(span: Span, key: str, count: int | None) -> None:
    if not count:
        return
    so_far = getattr(span, "attributes", None) or {}
    span.set_attribute(key, int(so_far.get(key, 0)) + count)
