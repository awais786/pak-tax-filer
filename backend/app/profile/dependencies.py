"""require_profile: for endpoints that need the user's tax year and ATL status (T040, R14).

Usage:  `profile: Annotated[TaxpayerProfile, Depends(require_profile)]`. A logged-in user
without a profile gets 409 "Set up your profile first." (the UI also sends them to /profile).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.db import get_db
from app.profile.models import TaxpayerProfile
from app.profile.service import get_profile

NO_PROFILE = "Set up your profile first."


async def require_profile(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxpayerProfile:
    """The logged-in user's profile; 409 if they haven't set one up (401 if not logged in)."""
    profile = await get_profile(db, user)
    if profile is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_PROFILE)
    return profile
