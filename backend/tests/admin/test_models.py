"""The admin area's tables (feature 011, task T004; specs/011-admin-area/data-model.md).

The test database is built by running the migrations, so these also prove 0009_admin_area.
"""

import uuid
from datetime import UTC, datetime

import pytest
from conftest import make_user
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditEntry
from app.telemetry.models import TelemetrySpan

pytestmark = pytest.mark.anyio


async def test_a_new_account_is_an_active_taxpayer(db: AsyncSession) -> None:
    """Fails if a new account starts as an admin or disabled (FR-001: admins only from the
    command line)."""
    user = await make_user(db, "taxpayer@example.com")
    await db.refresh(user)

    assert user.is_admin is False
    assert user.disabled_at is None


async def test_existing_accounts_got_the_safe_defaults(db: AsyncSession) -> None:
    """Fails if the migration's server defaults would make old rows admins or disabled."""
    await db.execute(
        text("INSERT INTO users (id, email, password_hash) VALUES (:id, :email, 'x')"),
        {"id": uuid.uuid4(), "email": "old@example.com"},
    )

    row = (
        await db.execute(
            text("SELECT is_admin, disabled_at FROM users WHERE email = 'old@example.com'")
        )
    ).one()

    assert row == (False, None)


async def test_an_audit_entry_round_trips_without_foreign_keys(db: AsyncSession) -> None:
    """Fails if an entry can't name accounts that don't exist (any more): no foreign keys, so the
    log survives deletions (FR-017)."""
    gone_admin, gone_target = uuid.uuid4(), uuid.uuid4()
    db.add(AdminAuditEntry(admin_id=gone_admin, action="view_account", target_user_id=gone_target))
    await db.flush()

    entry = (await db.execute(select(AdminAuditEntry))).scalar_one()

    assert (entry.admin_id, entry.action, entry.target_user_id) == (
        gone_admin,
        "view_account",
        gone_target,
    )
    assert entry.at is not None


async def test_a_telemetry_row_round_trips(db: AsyncSession) -> None:
    """Fails if a saved request or AI call loses any of its columns (data-model.md)."""
    now = datetime.now(UTC)
    db.add(
        TelemetrySpan(
            kind="ai",
            name="generate_content gemini-test",
            started_at=now,
            duration_ms=812.5,
            error=False,
            feature="extraction",
            model="gemini-test",
            operation="generate_content",
            outcome="passed",
            input_tokens=120,
            output_tokens=30,
        )
    )
    await db.flush()

    row = (await db.execute(select(TelemetrySpan))).scalar_one()

    assert (row.kind, row.feature, row.outcome, row.input_tokens, row.output_tokens) == (
        "ai",
        "extraction",
        "passed",
        120,
        30,
    )
    assert row.route is None and row.status_code is None
