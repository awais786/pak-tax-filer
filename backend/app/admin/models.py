"""The admin audit log table (feature 011, task T005; data-model.md; research R8).

One entry per admin action and per opening of an account's details: who, what, which account,
when, and nothing else (no email, figure or document content, FR-016). Insert-only: there is no
update or delete path, and no clean-up (FR-017). No foreign keys, so entries outlive the accounts
they name.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AdminAuditEntry(Base):
    """One thing an admin did or looked at."""

    __tablename__ = "admin_audit_log"
    __table_args__ = (Index("ix_admin_audit_log_at", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # No foreign key on either account (FR-017).
    admin_id: Mapped[uuid.UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(32))
    target_user_id: Mapped[uuid.UUID] = mapped_column()
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
