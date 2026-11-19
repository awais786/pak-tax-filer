"""Auth tables, exactly as specs/002-auth-foundation/data-model.md (feature 002, task T006).

No identity fields beyond the login email (constitution, Principle V).
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """Someone who can log in."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored trimmed and lower-cased, so uniqueness ignores letter case (FR-001).
    email: Mapped[str] = mapped_column(String, unique=True)
    # Argon2 hash, never the password (FR-003).
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Feature 011: a staff account made by `create-admin` (never set on a taxpayer account); it can
    # use the admin area and nothing else (FR-001, FR-002).
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Feature 011: set when an admin disables the account (null = active); refused everywhere.
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def can_use_app(self) -> bool:
        """An active taxpayer account: admins and disabled accounts are refused by the app's
        login, its sessions and access tokens, as if unknown (feature 011, FR-002, FR-014a)."""
        return not self.is_admin and self.disabled_at is None


class Session(Base):
    """Proof that a user is logged in; one per login (a user may have several)."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # SHA-256 of the cookie token; the token itself is never stored (research R2).
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # created_at + 7 days (FR-009).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginFailure(Base):
    """One failed login attempt, kept only for throttling (FR-007)."""

    __tablename__ = "login_failures"
    __table_args__ = (Index("ix_login_failures_email_attempted_at", "email", "attempted_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Trimmed and lower-cased, like users.email.
    email: Mapped[str] = mapped_column(String)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
