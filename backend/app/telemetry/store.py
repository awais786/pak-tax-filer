"""Saving telemetry for the admin area (feature 011, tasks T027, T029; FR-019 to FR-023;
research R9, R10).

OpenTelemetry finishes spans on its own export thread, but the database code is async, so the
exporter only turns each request or AI-call span into a plain row on a bounded in-memory queue;
a background task started with the app writes the queue every few seconds and deletes rows older
than 30 days. The exporter is added through `add_exporter`, behind the filter that keeps only the
content-free attributes in ALLOWED, and a row holds only data-model.md's columns. Nothing here
can fail or slow a request: export never raises, and write errors are logged by type only.
"""

import logging
from collections import deque
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import anyio
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, StatusCode
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.settings import telemetry_store
from app.telemetry.models import TelemetrySpan
from app.telemetry.setup import add_exporter

_log = logging.getLogger(__name__)

QUEUE_SIZE = 10_000
KEEP = timedelta(days=30)
Row = dict[str, Any]

# data-model.md's attribute columns: column -> the span attribute it comes from.
_ATTRIBUTES = {
    "route": "http.route",
    "method": "http.request.method",
    "status_code": "http.response.status_code",
    "feature": "app.feature",
    "model": "gen_ai.request.model",
    "operation": "gen_ai.operation.name",
    "outcome": "app.outcome",
    "input_tokens": "gen_ai.usage.input_tokens",
    "output_tokens": "gen_ai.usage.output_tokens",
}


def new_queue() -> deque[Row]:
    """A queue that drops its oldest rows when full (a stalled writer can't grow memory)."""
    return deque(maxlen=QUEUE_SIZE)


def _row(span: ReadableSpan) -> Row | None:
    """The row for a request or AI-call span; None for anything else (database spans)."""
    attributes = span.attributes or {}
    if "gen_ai.operation.name" in attributes:
        kind = "ai"
    elif span.kind == SpanKind.SERVER and "http.route" in attributes:
        kind = "request"
    else:
        return None
    if span.start_time is None or span.end_time is None:
        return None
    return {
        "kind": kind,
        "name": span.name,
        "started_at": datetime.fromtimestamp(span.start_time / 1e9, UTC),
        "duration_ms": (span.end_time - span.start_time) / 1e6,
        "error": span.status.status_code == StatusCode.ERROR,
        **{column: attributes.get(name) for column, name in _ATTRIBUTES.items()},
    }


class DatabaseSpanExporter(SpanExporter):
    """Queues one row per request or AI-call span."""

    def __init__(self, queue: deque[Row]) -> None:
        self._queue = queue

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Queue the rows; never raises (FR-020)."""
        try:
            for span in spans:
                row = _row(span)
                if row is not None:
                    self._queue.append(row)
        except Exception:  # pylint: disable=broad-exception-caught  # never fail the caller
            _log.warning("Telemetry rows could not be queued.")
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Nothing to close: the writer owns the database side."""


def enable(environ: Mapping[str, str]) -> deque[Row] | None:
    """Start queuing spans if TELEMETRY_STORE is on (the default); return the queue, else None."""
    if not telemetry_store(environ):
        return None
    queue = new_queue()
    add_exporter(DatabaseSpanExporter(queue))
    return queue


async def write_batch(db: AsyncSession, queue: deque[Row]) -> int:
    """Insert what's queued and commit; returns how many rows were saved. The inserts make no
    spans (instrumentation suppressed), and an error is logged by type and the batch dropped."""
    rows = []
    while queue:
        rows.append(queue.popleft())
    if not rows:
        return 0
    try:
        with suppress_instrumentation():
            await db.execute(insert(TelemetrySpan), rows)
            await db.commit()
    except Exception as error:  # pylint: disable=broad-exception-caught  # never stop the writer
        _log.warning("Saving %d telemetry rows failed (%s).", len(rows), type(error).__name__)
        with suppress_instrumentation():
            await db.rollback()
        return 0
    return len(rows)


async def delete_old(db: AsyncSession, now: datetime) -> int:
    """Delete rows older than 30 days and commit; returns how many went (FR-021)."""
    with suppress_instrumentation():
        result = await db.execute(
            delete(TelemetrySpan).where(TelemetrySpan.started_at < now - KEEP)
        )
        await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def _beat(
    sessions: async_sessionmaker[AsyncSession], queue: deque[Row], *, clean_up: bool
) -> None:
    """One write (and, now and then, the clean-up); shielded, so stopping the app never cuts a
    write off halfway and loses its batch."""
    with anyio.CancelScope(shield=True):
        async with sessions() as db:
            await write_batch(db, queue)
            if clean_up:
                try:
                    await delete_old(db, datetime.now(UTC))
                except Exception as error:  # pylint: disable=broad-exception-caught
                    _log.warning("Deleting old telemetry failed (%s).", type(error).__name__)


async def _run(
    sessions: async_sessionmaker[AsyncSession], queue: deque[Row], interval: float
) -> None:
    cleanups_every = max(1, int(3600 / interval))  # about once an hour
    beats = 0
    while True:
        await anyio.sleep(interval)
        await _safe_beat(sessions, queue, clean_up=beats % cleanups_every == 0)
        beats += 1


async def _safe_beat(
    sessions: async_sessionmaker[AsyncSession], queue: deque[Row], *, clean_up: bool
) -> None:
    """A beat that can't stop the writer: an error outside the write itself (opening or closing
    a session, a rollback) is logged by type and the next beat tries again (review L1)."""
    try:
        await _beat(sessions, queue, clean_up=clean_up)
    except Exception as error:  # pylint: disable=broad-exception-caught  # keep saving
        _log.warning("A telemetry write failed (%s).", type(error).__name__)


@asynccontextmanager
async def writer(
    sessions: async_sessionmaker[AsyncSession], queue: deque[Row], interval: float = 5.0
) -> AsyncIterator[None]:
    """Run the background writer while the context is open (the app's lifespan)."""
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(_run, sessions, queue, interval)
        try:
            yield
        finally:
            tasks.cancel_scope.cancel()
    await _safe_beat(sessions, queue, clean_up=False)  # what was queued since the last beat


# ---- The telemetry page's figures (T029; FR-022) ----

SLOWEST = 10


@dataclass(frozen=True)
class RouteTiming:
    """How long one page took: typical (median) and worst-case (95th percentile)."""

    route: str
    requests: int
    median_ms: float
    p95_ms: float


@dataclass(frozen=True)
class TelemetrySummary:  # pylint: disable=too-many-instance-attributes  # one field per figure
    """The last 30 days, as the telemetry page shows them."""

    requests_per_day: list[tuple[date, int]]
    server_error_share: float  # percent of requests answered 5xx
    slowest_routes: list[RouteTiming]
    ai_calls: list[tuple[str, str, int]]  # feature, outcome, calls
    ai_duration: list[tuple[str, float]]  # feature, median milliseconds
    tokens_per_day: list[tuple[date, int, int]]  # day, input, output


async def telemetry_summary(db: AsyncSession, now: datetime) -> TelemetrySummary:
    """FR-022's figures for the 30 days before `now` (days in UTC)."""
    recent = TelemetrySpan.started_at >= now - KEEP
    is_request = TelemetrySpan.kind == "request"
    is_ai = TelemetrySpan.kind == "ai"
    day = func.date(func.timezone("UTC", TelemetrySpan.started_at))
    median = func.percentile_cont(0.5).within_group(TelemetrySpan.duration_ms)
    p95 = func.percentile_cont(0.95).within_group(TelemetrySpan.duration_ms)

    per_day = await db.execute(
        select(day, func.count()).where(recent, is_request).group_by(day).order_by(day)
    )
    total, failed = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(TelemetrySpan.status_code >= 500),
            ).where(recent, is_request)
        )
    ).one()
    routes = await db.execute(
        select(TelemetrySpan.route, func.count(), median, p95)
        .where(recent, is_request)
        .group_by(TelemetrySpan.route)
        .order_by(p95.desc())
        .limit(SLOWEST)
    )
    calls = await db.execute(
        select(TelemetrySpan.feature, TelemetrySpan.outcome, func.count())
        .where(recent, is_ai)
        .group_by(TelemetrySpan.feature, TelemetrySpan.outcome)
        .order_by(TelemetrySpan.feature, TelemetrySpan.outcome)
    )
    durations = await db.execute(
        select(TelemetrySpan.feature, median)
        .where(recent, is_ai)
        .group_by(TelemetrySpan.feature)
        .order_by(TelemetrySpan.feature)
    )
    tokens = await db.execute(
        select(
            day,
            func.coalesce(func.sum(TelemetrySpan.input_tokens), 0),
            func.coalesce(func.sum(TelemetrySpan.output_tokens), 0),
        )
        .where(recent, is_ai, TelemetrySpan.input_tokens.is_not(None))
        .having(func.coalesce(func.sum(TelemetrySpan.input_tokens), 0) > 0)
        .group_by(day)
        .order_by(day)
    )
    return TelemetrySummary(
        requests_per_day=[(d, int(n)) for d, n in per_day],
        server_error_share=100.0 * failed / total if total else 0.0,
        slowest_routes=[
            RouteTiming(route or "", int(n), round(float(m), 1), round(float(p), 1))
            for route, n, m, p in routes
        ],
        ai_calls=[(feature or "", outcome or "", int(n)) for feature, outcome, n in calls],
        ai_duration=[(feature or "", round(float(m), 1)) for feature, m in durations],
        tokens_per_day=[(d, int(i), int(o)) for d, i, o in tokens],
    )
