"""The telemetry page (feature 011, task T028; FR-022, SC-007; research R10)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from admin_helpers import admin_client, make_admin, sign_in
from sqlalchemy.ext.asyncio import AsyncSession

from app.telemetry.models import TelemetrySpan
from app.telemetry.store import RouteTiming, telemetry_summary

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def request(day: int, route: str, ms: float, status: int = 200) -> TelemetrySpan:
    """A saved request `day` days before NOW."""
    return TelemetrySpan(
        kind="request",
        name=f"GET {route}",
        started_at=NOW - timedelta(days=day, hours=1),
        duration_ms=ms,
        error=status >= 500,
        route=route,
        method="GET",
        status_code=status,
    )


def ai(day: int, feature: str, outcome: str, ms: float, tokens: tuple[int, int]) -> TelemetrySpan:
    """A saved AI call `day` days before NOW."""
    return TelemetrySpan(
        kind="ai",
        name="generate_content gemini-test",
        started_at=NOW - timedelta(days=day, hours=1),
        duration_ms=ms,
        error=outcome != "passed",
        feature=feature,
        model="gemini-test",
        operation="generate_content",
        outcome=outcome,
        input_tokens=tokens[0],
        output_tokens=tokens[1],
    )


@pytest.fixture
async def saved(db: AsyncSession) -> None:
    """Requests and AI calls over three days, plus one row older than 30 days."""
    db.add_all(
        [
            request(0, "/api/tax/{tax_year}", 10),
            request(0, "/api/tax/{tax_year}", 20),
            request(0, "/api/tax/{tax_year}", 30, status=500),
            request(1, "/health", 1),
            request(2, "/health", 3),
            request(40, "/health", 999),  # outside the 30 days
            ai(0, "extraction", "passed", 800, (100, 20)),
            ai(0, "extraction", "timeout", 15000, (0, 0)),
            ai(1, "assistant", "passed", 400, (50, 10)),
        ]
    )
    await db.flush()


@pytest.mark.usefixtures("saved")
async def test_the_summary_matches_the_saved_rows(db: AsyncSession) -> None:
    """Fails if any of FR-022's figures differs from the rows of the last 30 days (SC-007)."""
    summary = await telemetry_summary(db, NOW)

    assert summary.requests_per_day == [
        (date(2026, 11, 15), 1),
        (date(2026, 11, 16), 1),
        (date(2026, 11, 17), 3),
    ]
    assert summary.server_error_share == pytest.approx(20.0)  # 1 of 5
    assert summary.slowest_routes[0] == RouteTiming("/api/tax/{tax_year}", 3, 20.0, 29.0)
    assert summary.ai_calls == [
        ("assistant", "passed", 1),
        ("extraction", "passed", 1),
        ("extraction", "timeout", 1),
    ]
    assert summary.ai_duration == [("assistant", 400.0), ("extraction", 7900.0)]
    assert summary.tokens_per_day == [(date(2026, 11, 16), 50, 10), (date(2026, 11, 17), 100, 20)]


async def test_an_empty_table_gives_an_empty_summary(db: AsyncSession) -> None:
    """Fails if a fresh install (no telemetry yet) breaks the page."""
    summary = await telemetry_summary(db, NOW)

    assert summary.requests_per_day == [] and summary.server_error_share == 0.0
    assert summary.slowest_routes == [] and summary.ai_calls == []


@pytest.mark.usefixtures("saved")
async def test_the_telemetry_page_shows_the_summary(db: AsyncSession) -> None:
    """Fails if the page lacks a section or a figure."""
    await make_admin(db)

    async with admin_client(db) as http:
        await sign_in(http)
        page = await http.get("/admin/telemetry")

    assert page.status_code == 200
    for text in (
        "Requests per day",
        "Server errors",
        "Slowest pages",
        "/api/tax/{tax_year}",
        "AI calls",
        "extraction",
        "timeout",
        "Tokens per day",
    ):
        assert text in page.text, text
