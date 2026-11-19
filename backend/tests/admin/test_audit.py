"""Recording admin actions and views (feature 011, task T010; FR-016, FR-017; research R8)."""

import uuid

import pytest
from conftest import make_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import audit
from app.admin.models import AdminAuditEntry
from app.auth.models import User

pytestmark = pytest.mark.anyio

ACTIONS = (
    "view_account",
    "disable",
    "enable",
    "delete_account",
    "sign_out_everywhere",
    "reset_reading_limit",
)


@pytest.mark.parametrize("action", ACTIONS)
async def test_each_action_is_recorded_once(db: AsyncSession, action: str) -> None:
    """Fails if an action isn't recorded, or is recorded with the wrong admin, account or time."""
    admin, target = uuid.uuid4(), uuid.uuid4()

    await audit.record(db, admin, action, target)

    entry = (await db.execute(select(AdminAuditEntry))).scalar_one()
    assert (entry.admin_id, entry.action, entry.target_user_id) == (admin, action, target)
    assert entry.at is not None


async def test_an_unknown_action_is_refused(db: AsyncSession) -> None:
    """Fails if a typo lands in the log as a new kind of action."""
    with pytest.raises(ValueError, match="unknown audit action"):
        await audit.record(db, uuid.uuid4(), "promote", uuid.uuid4())

    assert (await db.execute(select(AdminAuditEntry))).first() is None


def test_nothing_can_change_or_remove_an_entry() -> None:
    """Fails if the module grows a way to edit or delete the log (FR-017: insert-only)."""
    public = {name for name in dir(audit) if not name.startswith("_")}

    assert not {name for name in public if any(w in name for w in ("delete", "update", "remove"))}


async def test_entries_outlive_the_accounts_they_name(db: AsyncSession) -> None:
    """Fails if deleting the admin or the account removes the history (FR-017)."""
    admin = await make_user(db, "admin@example.com")
    target = await make_user(db, "taxpayer@example.com")
    await audit.record(db, admin.id, "disable", target.id)

    for user in (admin, target):
        await db.delete(user)
    await db.flush()

    assert (await db.execute(select(User))).first() is None
    entry = (await db.execute(select(AdminAuditEntry))).scalar_one()
    assert (entry.admin_id, entry.target_user_id) == (admin.id, target.id)
