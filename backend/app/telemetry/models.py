"""The saved-telemetry table (feature 011, task T005; data-model.md; research R9).

Request and AI-call spans, with only the attributes `setup.ALLOWED` lets through, kept 30 days for
the admin area's telemetry page. Never content: no prompt, reply, figure, email, id or path with
ids (feature 008's rule).
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TelemetrySpan(Base):
    """One request or AI call."""

    __tablename__ = "telemetry_spans"
    __table_args__ = (Index("ix_telemetry_spans_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))  # "request" or "ai"
    name: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float] = mapped_column(Float)
    error: Mapped[bool] = mapped_column(Boolean)
    route: Mapped[str | None] = mapped_column(String)
    method: Mapped[str | None] = mapped_column(String(16))
    status_code: Mapped[int | None] = mapped_column(Integer)
    feature: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String)
    operation: Mapped[str | None] = mapped_column(String(32))
    outcome: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
