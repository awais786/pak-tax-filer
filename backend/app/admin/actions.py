"""The admin actions on a taxpayer account (feature 011, task T023; FR-014 to FR-016; research R7).

Plain functions, so they can be tested without the admin pages. Each refuses an admin account
(admins are managed from the command line, so no admin can lock out another), does its work and
records one audit entry in the same transaction: an action that fails records nothing. None of
them changes a figure, confirms a document or edits a profile (Principle III).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import audit
from app.auth.models import Session, User
from app.documents.models import Document, ExtractionAttempt
from app.documents.service import DAILY_WINDOW
from app.documents.storage import Storage, StorageUnavailable
from app.tokens.models import PersonalAccessToken

STORAGE_DOWN = "Storage can't be reached; nothing was deleted. Try again later."


class AccountGone(Exception):
    """The account doesn't exist (any more)."""


class TargetIsAdmin(Exception):
    """The account is an admin's: the actions apply to taxpayer accounts only."""


class StorageDown(Exception):
    """File storage couldn't be reached, so the account was not deleted."""


async def _taxpayer(db: AsyncSession, user_id: uuid.UUID, *, lock: bool = False) -> User:
    query = select(User).where(User.id == user_id)
    if lock:  # held until the transaction ends
        query = query.with_for_update().execution_options(populate_existing=True)
    user = (await db.execute(query)).scalar_one_or_none()
    if user is None:
        raise AccountGone("That account no longer exists.")
    if user.is_admin:
        raise TargetIsAdmin("Admin accounts are managed from the command line.")
    return user


async def _end_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(Session).where(Session.user_id == user_id))


async def disable_account(db: AsyncSession, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Mark the account disabled and remove its sessions and access tokens (FR-014a)."""
    user = await _taxpayer(db, user_id)
    if user.disabled_at is None:
        user.disabled_at = datetime.now(UTC)
    await _end_sessions(db, user_id)
    await db.execute(delete(PersonalAccessToken).where(PersonalAccessToken.user_id == user_id))
    await audit.record(db, admin_id, "disable", user_id)


async def enable_account(db: AsyncSession, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Let the account sign in again; its old tokens stay removed (FR-014b)."""
    user = await _taxpayer(db, user_id)
    user.disabled_at = None
    await audit.record(db, admin_id, "enable", user_id)


async def delete_account(
    db: AsyncSession, storage: Storage, admin_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Remove every stored file first, then the account and everything that cascades from it
    (FR-014c). If storage can't be reached, no record is touched; a retry is safe, since a file
    already removed counts as removed.

    The account row is locked first (review M1): an upload still in flight (its document row not
    yet committed) finishes before the files are read, and a later one fails on its foreign key
    and removes its own file, so no file is left behind."""
    user = await _taxpayer(db, user_id, lock=True)
    locations = (
        await db.execute(select(Document.file_path).where(Document.user_id == user_id))
    ).scalars()
    try:
        for location in locations:
            await storage.delete(location)
    except StorageUnavailable as down:
        raise StorageDown(STORAGE_DOWN) from down
    await db.delete(user)
    await db.flush()
    await audit.record(db, admin_id, "delete_account", user_id)


async def sign_out_everywhere(db: AsyncSession, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """End every session of the account; its access tokens keep working (FR-014d)."""
    await _taxpayer(db, user_id)
    await _end_sessions(db, user_id)
    await audit.record(db, admin_id, "sign_out_everywhere", user_id)


async def reset_reading_limit(db: AsyncSession, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Clear the account's document readings counted in the last 24 hours (FR-014e)."""
    await _taxpayer(db, user_id)
    since = datetime.now(UTC) - DAILY_WINDOW
    await db.execute(
        delete(ExtractionAttempt).where(
            ExtractionAttempt.user_id == user_id, ExtractionAttempt.attempted_at > since
        )
    )
    await audit.record(db, admin_id, "reset_reading_limit", user_id)
