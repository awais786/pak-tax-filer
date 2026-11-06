"""Reading and saving the taxpayer profile (feature 002, task T039, research R11).

Other features read the profile with get_profile (or refuse with require_profile).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.profile.models import TaxpayerProfile
from app.settings import SUPPORTED_TAX_YEARS


async def get_profile(db: AsyncSession, user: User) -> TaxpayerProfile | None:
    """The user's profile, or None if they haven't set one up."""
    return (
        await db.execute(select(TaxpayerProfile).where(TaxpayerProfile.user_id == user.id))
    ).scalar_one_or_none()


async def save_profile(
    db: AsyncSession, user: User, tax_year: str, *, on_atl: bool
) -> TaxpayerProfile:
    """Create or replace the user's profile; raises ValueError for an unsupported tax year.

    One INSERT ... ON CONFLICT (user_id) DO UPDATE, so two saves arriving together still leave
    exactly one profile: the last one wins.
    """
    if tax_year not in SUPPORTED_TAX_YEARS:
        raise ValueError(f"Tax year {tax_year} is not supported.")

    saved_at = datetime.now(UTC)  # one clock for both create and update (review L5)
    upsert = (
        insert(TaxpayerProfile)
        .values(user_id=user.id, tax_year=tax_year, on_atl=on_atl, updated_at=saved_at)
        .on_conflict_do_update(
            index_elements=[TaxpayerProfile.user_id],
            # The save time itself, not PostgreSQL now() (which is the transaction start).
            set_={"tax_year": tax_year, "on_atl": on_atl, "updated_at": saved_at},
        )
        .returning(TaxpayerProfile)
    )
    # populate_existing refreshes a profile already loaded in this session with the new values.
    result = await db.execute(upsert, execution_options={"populate_existing": True})
    profile: TaxpayerProfile = result.scalar_one()
    await db.flush()
    return profile
