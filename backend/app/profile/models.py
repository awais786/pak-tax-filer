"""The taxpayer_profiles table, exactly as specs/002-auth-foundation/data-model.md (T038).

No identity or residency fields: no name, CNIC or NTN (FR-018, constitution Principle V).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaxpayerProfile(Base):
    """A user's tax year and ATL status; at most one per user."""

    __tablename__ = "taxpayer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # One profile per user (FR-016); deleted with the user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # One of SUPPORTED_TAX_YEARS, checked on save (FR-017).
    tax_year: Mapped[str] = mapped_column(String)
    # On FBR's Active Taxpayers' List; required, no "unknown" (FR-016).
    on_atl: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set on every save.
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
