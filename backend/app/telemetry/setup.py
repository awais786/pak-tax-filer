"""OpenTelemetry setup (feature 008, task T019; research R1-R2, FR-010, FR-012, FR-013).

Spans go to the backend logs (the console exporter) unless OTEL_EXPORTER is "none"; there is no
viewer in 008, and telemetry is for developers only. Requests are named by route template and
database spans keep no statement text. Every exporter gets spans through `_Filtered`, which
keeps only the attributes in ALLOWED and drops events (an exception's message can hold content)
and status descriptions: user content can't reach the logs even if an instrumentation adds it.
"""

import os
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import SpanKind, Status, StatusCode
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.settings import otel_exporter

_db_tracer = trace.get_tracer("app.db")

# Everything a span may keep (data-model "Telemetry span attributes"). Anything else an
# instrumentation records (full URLs, client addresses, SQL text, ...) is dropped.
ALLOWED = frozenset(
    {
        "http.request.method",
        "http.route",
        "http.response.status_code",
        "db.system.name",
        "gen_ai.provider.name",
        "gen_ai.operation.name",
        "gen_ai.request.model",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.tool.name",
        "app.feature",
        "app.outcome",
    }
)


def exporter_for(name: str) -> SpanExporter | None:
    """The exporter OTEL_EXPORTER names: the logs ("console", the default) or none."""
    return ConsoleSpanExporter() if name == "console" else None


class _Filtered(SpanProcessor):
    """Hands an exporter's processor a copy of each span with only the allowed attributes."""

    def __init__(self, inner: SpanProcessor) -> None:
        self._inner = inner

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        """Nothing to filter yet: attributes are checked when the span ends."""
        del span, parent_context

    def on_end(self, span: ReadableSpan) -> None:
        """Pass on the filtered copy."""
        self._inner.on_end(_filtered(span))

    def shutdown(self) -> None:
        """Shut the exporter's processor down."""
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Flush the exporter's processor."""
        return self._inner.force_flush(timeout_millis)


def _filtered(span: ReadableSpan) -> ReadableSpan:
    attributes = {k: v for k, v in (span.attributes or {}).items() if k in ALLOWED}
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        kind=span.kind,
        status=Status(span.status.status_code),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


@lru_cache(maxsize=1)
def _provider() -> TracerProvider:
    """The process's tracer provider, made and registered once."""
    # The current names for HTTP attributes (http.request.method, http.response.status_code)
    # rather than the older ones; read by the instrumentations when they start.
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    provider = TracerProvider(resource=Resource.create({"service.name": "pak-tax-filer-backend"}))
    trace.set_tracer_provider(provider)
    return provider


def add_exporter(exporter: SpanExporter, *, batch: bool = True) -> None:
    """Send spans to an exporter, through the filter: the only way any exporter is added (the
    logs' own, and tests' in-memory one), so none can get unfiltered spans."""
    inner = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
    _provider().add_span_processor(_Filtered(inner))


@lru_cache(maxsize=1)
def _logs() -> None:
    """The logs' exporter, added once (unless OTEL_EXPORTER is "none")."""
    # Read on its own, not through get_settings(), so importing the app needs no DATABASE_URL.
    exporter = exporter_for(otel_exporter(os.environ))
    if exporter is not None:
        add_exporter(exporter)


def configure(app: FastAPI) -> None:
    """Spans to the logs, and the app's requests instrumented (engines: `instrument_engine`)."""
    _logs()
    # One span per request, not one per ASGI message as well.
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=_provider(), exclude_spans=["receive", "send"]
    )


# ---- Database spans ----
# Our own few lines rather than opentelemetry-instrumentation-sqlalchemy, which doesn't support
# SQLAlchemy 2.1 (it silently records nothing): a span per statement with its duration and the
# operation's first word, never the statement text or its parameters (research R2, amended).

_OPERATIONS = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "BEGIN", "COMMIT"})
_SPAN = "_telemetry_span"


def instrument_engine(engine: AsyncEngine) -> AsyncEngine:
    """Record a duration span for each statement the engine runs."""
    sync = engine.sync_engine
    if not event.contains(sync, "before_cursor_execute", _before):
        event.listen(sync, "before_cursor_execute", _before)
        event.listen(sync, "after_cursor_execute", _after)
        event.listen(sync, "handle_error", _failed)
    return engine


def _before(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    del conn, cursor, parameters, executemany
    words = statement.split(None, 1)
    operation = words[0].upper() if words else ""
    span = _db_tracer.start_span(
        operation if operation in _OPERATIONS else "db.query",
        kind=SpanKind.CLIENT,
        attributes={"db.system.name": "postgresql"},
    )
    setattr(context, _SPAN, span)


def _after(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    del conn, cursor, statement, parameters, executemany
    _end(context)


def _failed(exception_context: Any) -> None:
    _end(exception_context.execution_context, failed=True)


def _end(context: Any, *, failed: bool = False) -> None:
    span = getattr(context, _SPAN, None)
    if span is not None:
        if failed:
            span.set_status(Status(StatusCode.ERROR))  # the code only: no error text
        span.end()
        setattr(context, _SPAN, None)
