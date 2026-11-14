"""PDF exports (feature 008, task T007; contracts/pdf-and-telemetry.md, FR-001 to FR-007).

Each PDF has the same protection as the result it exports (login, profile, the caller's own
data), is built from that same result recalculated now, and is never stored. Blocked, not-ready
and unapproved results export nothing (409 with the reason). No AI-written text is included.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.db import get_db
from app.documents.service import confirmed_documents
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.reports.render import render_pdf
from app.reports.status import (
    PAKISTAN,
    banner_head,
    tax_status,
    wealth_status,
    workflow_status,
)
from app.tax.engine import calculate
from app.tax.rates import rates_for
from app.tax.router import tax_out
from app.tax.service import BLOCKED_MESSAGES, tax_inputs_from
from app.wealth.service import wealth_view
from app.workflow import service as workflow
from app.workflow.router import APPROVAL_NEEDED, Ctx

router = APIRouter(tags=["reports"])

CurrentUser = Annotated[User, Depends(current_user)]
Profile = Annotated[TaxpayerProfile, Depends(require_profile)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _pdf(content: bytes, filename: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _known_year(tax_year: str) -> None:
    try:
        rates_for(tax_year)
    except KeyError as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rates for that tax year.") from missing


def _today() -> datetime:
    """Today in Pakistan (the "generated" date)."""
    return datetime.now(PAKISTAN)


@router.get("/api/tax/{tax_year}/pdf")
async def tax_pdf(tax_year: str, user: CurrentUser, profile: Profile, db: DbSession) -> Response:
    """004's result as a PDF; 409 with the reason when 004 refuses to calculate."""
    _known_year(tax_year)
    documents = await confirmed_documents(db, user.id, tax_year)  # one read for both
    result = calculate(tax_inputs_from(documents, tax_year, profile.on_atl), rates_for(tax_year))
    if result.blocked_reason is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, BLOCKED_MESSAGES[result.blocked_reason])
    banner = [*banner_head(tax_year, _today()), *tax_status(documents, tax_year)]
    await db.commit()  # end the read transaction; nothing waits in it while the PDF renders
    content = await render_pdf("tax.html", banner=banner, result=tax_out(result), passages=[])
    return _pdf(content, f"tax-{tax_year}.pdf")


@router.get("/api/wealth/{tax_year}/pdf")
async def wealth_pdf(tax_year: str, user: CurrentUser, profile: Profile, db: DbSession) -> Response:
    """005's statement and reconciliation as a PDF; 409 with 005's reason when not ready."""
    del profile  # required (409 without one), as for the other exports
    _known_year(tax_year)
    wealth = await wealth_view(db, user.id, tax_year)
    if wealth.result.not_ready_reason is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, wealth.result.message or "Not ready.")
    banner = [*banner_head(tax_year, _today()), *wealth_status(wealth.auto_filled)]
    await db.commit()  # end the read transaction; nothing waits in it while the PDF renders
    content = await render_pdf("wealth.html", banner=banner, wealth=wealth)
    return _pdf(content, f"wealth-{tax_year}.pdf")


@router.get("/api/workflow/result/pdf")
async def workflow_pdf(ctx: Ctx) -> Response:
    """007's approved result as a PDF with the approval date and the cited passages (not the
    research note, which the AI wrote); 409 unless approved for the current inputs."""
    found = await workflow.result(ctx)
    if found is None:
        raise HTTPException(status.HTTP_409_CONFLICT, APPROVAL_NEEDED)
    run, tax, documents = found
    if tax.blocked_reason is not None:  # approved, but 004 refuses to calculate (FR-007)
        raise HTTPException(status.HTTP_409_CONFLICT, BLOCKED_MESSAGES[tax.blocked_reason])
    assert run.approved_at is not None  # result() checked the approval
    tax_year = ctx.profile.tax_year
    banner = [
        *banner_head(tax_year, _today()),
        *workflow_status(documents, tax_year, run.approved_at),
    ]
    passages = ((run.step_outputs or {}).get("research") or {}).get("passages", [])
    await ctx.db.commit()  # end the read transaction; nothing waits in it while the PDF renders
    content = await render_pdf("tax.html", banner=banner, result=tax_out(tax), passages=passages)
    return _pdf(content, f"tax-{tax_year}.pdf")
