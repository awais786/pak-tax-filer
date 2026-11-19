"""Saving telemetry in the database (feature 011, task T026; FR-019 to FR-021, FR-023;
research R9; data-model.md, telemetry_spans)."""

from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanKind, Status, StatusCode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telemetry_helpers import Spans

from app.telemetry import store
from app.telemetry.models import TelemetrySpan

pytestmark = pytest.mark.anyio

COLUMNS = {
    "kind",
    "name",
    "started_at",
    "duration_ms",
    "error",
    "route",
    "method",
    "status_code",
    "feature",
    "model",
    "operation",
    "outcome",
    "input_tokens",
    "output_tokens",
}
START = 1_763_000_000_000_000_000  # nanoseconds since the epoch


def span(
    name: str,
    kind: SpanKind,
    attributes: dict[str, Any],
    *,
    duration_ms: float = 12.5,
    error: bool = False,
) -> ReadableSpan:
    """A finished span as OpenTelemetry hands it to an exporter."""
    return ReadableSpan(
        name=name,
        kind=kind,
        attributes=attributes,
        start_time=START,
        end_time=START + int(duration_ms * 1_000_000),
        status=Status(StatusCode.ERROR if error else StatusCode.UNSET),
    )


REQUEST = span(
    "GET /api/tax/{tax_year}",
    SpanKind.SERVER,
    {
        "http.request.method": "GET",
        "http.route": "/api/tax/{tax_year}",
        "http.response.status_code": 200,
    },
)
AI_CALL = span(
    "generate_content gemini-test",
    SpanKind.CLIENT,
    {
        "gen_ai.provider.name": "gcp.gemini",
        "gen_ai.operation.name": "generate_content",
        "gen_ai.request.model": "gemini-test",
        "gen_ai.usage.input_tokens": 120,
        "gen_ai.usage.output_tokens": 30,
        "app.feature": "extraction",
        "app.outcome": "passed",
    },
    duration_ms=800.0,
)
DATABASE = span("SELECT", SpanKind.CLIENT, {"db.system.name": "postgresql"})


def test_request_and_ai_spans_become_rows_and_database_spans_are_skipped() -> None:
    """Fails if a request or AI call isn't kept, a database span is (volume), or a column is
    filled wrongly (FR-019)."""
    queue: deque[dict[str, Any]] = deque(maxlen=10)

    store.DatabaseSpanExporter(queue).export([REQUEST, AI_CALL, DATABASE])

    request, ai = list(queue)
    assert request["kind"] == "request" and request["route"] == "/api/tax/{tax_year}"
    assert (request["method"], request["status_code"], request["error"]) == ("GET", 200, False)
    assert request["duration_ms"] == pytest.approx(12.5)
    assert request["started_at"] == datetime.fromtimestamp(START / 1e9, UTC)
    assert ai["kind"] == "ai" and (ai["feature"], ai["outcome"], ai["model"]) == (
        "extraction",
        "passed",
        "gemini-test",
    )
    assert (ai["input_tokens"], ai["output_tokens"]) == (120, 30)


def test_a_row_holds_only_the_data_model_s_columns() -> None:
    """Fails if anything beyond data-model.md's columns could be saved, e.g. an attribute an
    instrumentation adds (FR-019: nothing but the permitted details)."""
    leaky = span(
        "POST /api/auth/login",
        SpanKind.SERVER,
        {"http.route": "/api/auth/login", "user.email": "alice@example.com", "url.full": "x"},
    )
    queue: deque[dict[str, Any]] = deque(maxlen=10)

    store.DatabaseSpanExporter(queue).export([leaky])

    [row] = queue
    assert set(row) == COLUMNS
    assert "alice@example.com" not in repr(row)


def test_the_queue_is_bounded_and_drops_the_oldest() -> None:
    """Fails if a stalled writer could grow memory without limit on the 1 GB server."""
    queue = store.new_queue()

    store.DatabaseSpanExporter(queue).export([REQUEST] * (store.QUEUE_SIZE + 5))

    assert len(queue) == store.QUEUE_SIZE == 10_000


def test_exporting_never_raises() -> None:
    """Fails if a broken span could fail the code that finished it (FR-020)."""
    broken = ReadableSpan(name="x", kind=SpanKind.SERVER, attributes={"http.route": "/x"})

    result = store.DatabaseSpanExporter(deque(maxlen=10)).export([broken])

    assert result is not None


async def test_a_batch_is_written_without_making_spans_of_its_own(
    db: AsyncSession, spans: Spans
) -> None:
    """Fails if the queued rows aren't saved, or saving them creates database spans that would
    themselves be saved (a feedback loop)."""
    queue = store.new_queue()
    store.DatabaseSpanExporter(queue).export([REQUEST, AI_CALL])

    written = await store.write_batch(db, queue)

    assert written == 2 and not queue
    assert (await db.execute(select(func.count()).select_from(TelemetrySpan))).scalar_one() == 2
    assert not [s for s in spans.all() if s.name == "INSERT"]


async def test_a_failing_write_is_logged_without_content_and_does_not_raise(
    db: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Fails if a write error escapes the writer, or its log line carries row content."""
    queue = store.new_queue()
    queue.append({column: None for column in COLUMNS} | {"name": "alice@example.com"})

    written = await store.write_batch(db, queue)

    assert written == 0
    assert "alice@example.com" not in caplog.text
    assert "telemetry" in caplog.text.lower()


async def test_rows_older_than_30_days_are_deleted(db: AsyncSession) -> None:
    """Fails if old rows stay, or recent ones go (FR-021)."""
    now = datetime.now(UTC)
    for age in (timedelta(days=31), timedelta(days=29)):
        db.add(
            TelemetrySpan(
                kind="request", name="GET /", started_at=now - age, duration_ms=1.0, error=False
            )
        )
    await db.flush()

    deleted = await store.delete_old(db, now)

    assert deleted == 1
    kept = (await db.execute(select(TelemetrySpan.started_at))).scalars().all()
    assert kept == [now - timedelta(days=29)]


def test_saving_is_off_unless_turned_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails if TELEMETRY_STORE=off still adds the exporter, or on doesn't (FR-019, FR-023)."""
    added: list[object] = []
    monkeypatch.setattr(store, "add_exporter", lambda exporter, **_: added.append(exporter))

    assert store.enable({"TELEMETRY_STORE": "off"}) is None
    queue = store.enable({"TELEMETRY_STORE": "on"})

    assert queue is not None and len(added) == 1
    assert isinstance(added[0], store.DatabaseSpanExporter)


async def test_the_writer_saves_the_queue_in_the_background(db: AsyncSession) -> None:
    """Fails if the background writer started with the app doesn't save queued rows."""
    connection = await db.connection()
    sessions = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    queue = store.new_queue()

    now = int(datetime.now(UTC).timestamp() * 1e9)  # recent, so the first clean-up keeps it
    recent = ReadableSpan(
        name=REQUEST.name,
        kind=REQUEST.kind,
        attributes=REQUEST.attributes,
        start_time=now,
        end_time=now + 5_000_000,
        status=REQUEST.status,
    )

    async with store.writer(sessions, queue, interval=0.01):
        store.DatabaseSpanExporter(queue).export([recent])
        with anyio.fail_after(5):
            while queue:
                await anyio.sleep(0.01)
            await anyio.sleep(0.05)

    assert (await db.execute(select(func.count()).select_from(TelemetrySpan))).scalar_one() == 1


async def test_stopping_the_writer_saves_what_is_still_queued(db: AsyncSession) -> None:
    """Fails if rows queued since the last write are lost when the app stops."""
    connection = await db.connection()
    sessions = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    queue = store.new_queue()
    now = int(datetime.now(UTC).timestamp() * 1e9)

    async with store.writer(sessions, queue, interval=3600):
        store.DatabaseSpanExporter(queue).export(
            [
                ReadableSpan(
                    name="GET /",
                    kind=SpanKind.SERVER,
                    attributes={"http.route": "/"},
                    start_time=now,
                    end_time=now + 1,
                    status=Status(StatusCode.UNSET),
                )
            ]
        )

    assert (await db.execute(select(func.count()).select_from(TelemetrySpan))).scalar_one() == 1


async def test_the_app_runs_the_writer_while_saving_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails if the app's lifespan doesn't run the writer when telemetry is saved, or runs it
    when it isn't (tests and TELEMETRY_STORE=off)."""
    from app import main  # pylint: disable=import-outside-toplevel

    started: list[object] = []

    @asynccontextmanager
    async def fake_writer(_sessions: object, queue: object) -> AsyncIterator[None]:
        started.append(queue)
        yield

    monkeypatch.setattr(main, "telemetry_writer", fake_writer)
    queue = store.new_queue()
    for saving, expected in ((None, []), (queue, [queue])):
        started.clear()
        monkeypatch.setattr(main, "TELEMETRY_QUEUE", saving)
        async with main.lifespan(main.app):
            pass
        assert started == expected


async def test_the_writer_survives_an_error_outside_the_write(db: AsyncSession) -> None:
    """Fails if an error opening a session (or rolling back) stops saving for good (review L1):
    the next beat must still save."""
    connection = await db.connection()
    real = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    calls = 0

    def sessions() -> AsyncSession:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("database not ready")
        return real()

    queue = store.new_queue()
    now = int(datetime.now(UTC).timestamp() * 1e9)
    store.DatabaseSpanExporter(queue).export(
        [
            ReadableSpan(
                name="GET /",
                kind=SpanKind.SERVER,
                attributes={"http.route": "/"},
                start_time=now,
                end_time=now + 1,
                status=Status(StatusCode.UNSET),
            )
        ]
    )

    async with store.writer(sessions, queue, interval=0.01):  # type: ignore[arg-type]
        with anyio.fail_after(5):
            while calls < 3:
                await anyio.sleep(0.01)

    assert (await db.execute(select(func.count()).select_from(TelemetrySpan))).scalar_one() == 1
