"""Recording what admins do and look at (feature 011, task T011; FR-016, FR-017; research R8).

Insert-only by design: this module has no way to change or remove an entry, and nothing cleans
the log up. Callers record inside the same transaction as the action itself, so an action that
fails records nothing.
"""

import uuid
from typing import Literal, get_args

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditEntry

Action = Literal[
    "view_account",
    "disable",
    "enable",
    "delete_account",
    "sign_out_everywhere",
    "reset_reading_limit",
]
ACTIONS: frozenset[str] = frozenset(get_args(Action))


async def record(
    db: AsyncSession, admin_id: uuid.UUID, action: str, target_user_id: uuid.UUID
) -> None:
    """Add one entry: which admin did what to which account (now). No content (FR-016)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action: {action!r}")
    db.add(AdminAuditEntry(admin_id=admin_id, action=action, target_user_id=target_user_id))
    await db.flush()
