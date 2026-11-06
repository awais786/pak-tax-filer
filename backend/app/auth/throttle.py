"""Login throttling (feature 002, task T014, FR-007, research R4).

After 10 failed logins for an email within 15 minutes, further attempts for that email are
refused until the 15 minutes pass. Unknown emails are counted the same way, so throttling never
reveals which emails are registered. Stored in the database, so it survives restarts.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginFailure

MAX_FAILURES = 10
WINDOW = timedelta(minutes=15)


async def one_attempt_at_a_time(db: AsyncSession, email: str) -> None:
    """Hold a per-email lock until this transaction ends (PostgreSQL advisory lock).

    Throttling reads the failure count, checks the password, then records a failure. Without
    the lock, attempts sent at the same moment all read the count before any records a failure,
    and all get checked. A unique constraint can't express "10 failures in 15 minutes", so the
    usual insert-and-catch-IntegrityError pattern doesn't fit; the lock must last until the
    failure is recorded, so it is transaction-scoped (review M2; PR #27 review, item 6).
    """
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 0))"), {"email": email}
    )


async def is_throttled(db: AsyncSession, email: str) -> bool:
    """True if this (normalised) email has 10 or more failures in the last 15 minutes."""
    since = datetime.now(UTC) - WINDOW
    failures = (
        await db.execute(
            select(func.count())
            .select_from(LoginFailure)
            .where(LoginFailure.email == email, LoginFailure.attempted_at > since)
        )
    ).scalar_one()
    return failures >= MAX_FAILURES


async def record_failure(db: AsyncSession, email: str) -> None:
    """Remember one failed attempt for this (normalised) email."""
    db.add(LoginFailure(email=email, attempted_at=datetime.now(UTC)))
    await db.flush()
