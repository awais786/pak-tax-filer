"""What the admin dashboard and account page show (feature 011, task T015; FR-006, FR-008, FR-009;
research R6).

Plain read-only queries: nothing here writes, and a guided run is read as stored (never through
`workflow.service.get_run`, which re-runs the steps and saves). The tax result is computed exactly
as the Tax page computes it, from confirmed documents only (Principle III).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.auth.models import User
from app.documents.models import Document, ExtractionAttempt
from app.documents.service import APP_DAILY_EXTRACTIONS, DAILY_EXTRACTIONS, DAILY_WINDOW
from app.profile.models import TaxpayerProfile
from app.rag.models import AskRequest
from app.rag.service import HOURLY_LIMIT
from app.settings import SUPPORTED_TAX_YEARS, get_settings
from app.tax.engine import calculate
from app.tax.rates import rates_for
from app.tax.router import TaxOut, tax_out
from app.tax.service import tax_inputs
from app.workflow.models import WorkflowRun


@dataclass(frozen=True)
class Limit:
    """How much of a limit is used."""

    used: int
    limit: int


@dataclass(frozen=True)
class DashboardCounts:  # pylint: disable=too-many-instance-attributes  # one field per count
    """The dashboard's headline numbers (FR-006)."""

    taxpayers: int
    profiles: int
    documents: dict[str, int]
    runs_per_step: dict[str, int]
    readings_app: Limit
    readings_busiest_user: Limit
    questions_app: Limit
    questions_busiest_user_hour: Limit


@dataclass(frozen=True)
class DocumentLine:
    """One document as the account page lists it (no file, no figures)."""

    doc_type: str
    status: str
    tax_year: str
    uploaded_at: datetime


@dataclass(frozen=True)
class AccountOverview:
    """One account's progress (FR-008)."""

    tax_year: str | None
    on_atl: bool | None
    documents: list[DocumentLine]
    tax: TaxOut
    guided_step: str | None


async def _count(db: AsyncSession, query: Select[int]) -> int:
    return int((await db.execute(query)).scalar_one())


async def _busiest(
    db: AsyncSession,
    column: InstrumentedAttribute[datetime],
    user_column: InstrumentedAttribute[uuid.UUID],
    since: datetime,
) -> int:
    """The most rows any one user has since `since` (0 if none)."""
    per_user = (
        select(func.count().label("n")).where(column > since).group_by(user_column).subquery()
    )
    return int((await db.execute(select(func.coalesce(func.max(per_user.c.n), 0)))).scalar_one())


async def dashboard_counts(db: AsyncSession) -> DashboardCounts:
    """FR-006's counts, as of now."""
    now = datetime.now(UTC)
    day, hour = now - DAILY_WINDOW, now - timedelta(hours=1)
    documents = dict(
        (status.value, n)
        for status, n in (
            await db.execute(select(Document.status, func.count()).group_by(Document.status))
        ).all()
    )
    runs = dict(
        (step.value, n)
        for step, n in (
            await db.execute(select(WorkflowRun.step, func.count()).group_by(WorkflowRun.step))
        ).all()
    )
    return DashboardCounts(
        taxpayers=await _count(
            db, select(func.count()).select_from(User).where(User.is_admin.is_(False))
        ),
        profiles=await _count(db, select(func.count()).select_from(TaxpayerProfile)),
        documents=documents,
        runs_per_step=runs,
        readings_app=Limit(
            await _count(
                db,
                select(func.count())
                .select_from(ExtractionAttempt)
                .where(ExtractionAttempt.attempted_at > day),
            ),
            APP_DAILY_EXTRACTIONS,
        ),
        readings_busiest_user=Limit(
            await _busiest(db, ExtractionAttempt.attempted_at, ExtractionAttempt.user_id, day),
            DAILY_EXTRACTIONS,
        ),
        questions_app=Limit(
            await _count(
                db, select(func.count()).select_from(AskRequest).where(AskRequest.created_at > day)
            ),
            get_settings().ask_daily_limit,
        ),
        questions_busiest_user_hour=Limit(
            await _busiest(db, AskRequest.created_at, AskRequest.user_id, hour), HOURLY_LIMIT
        ),
    )


async def account_overview(db: AsyncSession, user: User) -> AccountOverview:
    """One account's tax year and ATL status, documents, tax result and guided-run step."""
    profile = (
        await db.execute(select(TaxpayerProfile).where(TaxpayerProfile.user_id == user.id))
    ).scalar_one_or_none()
    # Without a profile the Tax page refuses ("set your ATL status"); any supported year shows it.
    tax_year = profile.tax_year if profile else SUPPORTED_TAX_YEARS[0]
    documents = (
        await db.execute(
            select(Document).where(Document.user_id == user.id).order_by(Document.created_at)
        )
    ).scalars()
    step = (
        await db.execute(
            select(WorkflowRun.step).where(
                WorkflowRun.user_id == user.id, WorkflowRun.tax_year == tax_year
            )
        )
    ).scalar_one_or_none()
    return AccountOverview(
        tax_year=profile.tax_year if profile else None,
        on_atl=profile.on_atl if profile else None,
        documents=[
            DocumentLine(d.doc_type.value, d.status.value, d.tax_year, d.created_at)
            for d in documents
        ],
        tax=tax_out(calculate(await tax_inputs(db, user, tax_year), rates_for(tax_year))),
        guided_step=step.value if step else None,
    )
