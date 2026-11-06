"""GET/PUT /api/profile (feature 002, task T040).

Contract: the taxpayer-profile section of specs/002-auth-foundation/contracts/auth-api.md.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.profile.models import TaxpayerProfile
from app.profile.service import get_profile, save_profile
from app.settings import SUPPORTED_TAX_YEARS

router = APIRouter(prefix="/api/profile", tags=["profile"])

CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


class ProfileBody(BaseModel):
    """The profile's two answers. Unknown fields (e.g. a CNIC) are refused (FR-018), and
    on_atl must be a real true/false, never "yes" or null (FR-016)."""

    model_config = ConfigDict(extra="forbid")

    tax_year: str
    on_atl: StrictBool


class ProfileOut(BaseModel):
    """A saved profile as the API shows it."""

    tax_year: str
    on_atl: bool
    updated_at: datetime


class ProfileState(BaseModel):
    """GET /api/profile: the profile (or null) and the years the user can choose from."""

    profile: ProfileOut | None
    supported_tax_years: list[str]


def _out(profile: TaxpayerProfile) -> ProfileOut:
    return ProfileOut(
        tax_year=profile.tax_year, on_atl=profile.on_atl, updated_at=profile.updated_at
    )


@router.get("")
async def read_profile(user: CurrentUser, db: DbSession) -> ProfileState:
    """Always 200: "no profile yet" is a normal state for the setup page (research R13)."""
    profile = await get_profile(db, user)
    return ProfileState(
        profile=_out(profile) if profile else None,
        supported_tax_years=list(SUPPORTED_TAX_YEARS),
    )


@router.put("", dependencies=[Depends(require_json)])
async def write_profile(body: ProfileBody, user: CurrentUser, db: DbSession) -> ProfileOut:
    """Create or replace the caller's own profile (FR-021, FR-023)."""
    try:
        profile = await save_profile(db, user, body.tax_year, on_atl=body.on_atl)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    await db.commit()
    return _out(profile)
