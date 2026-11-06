"""app.profile.service: one profile per user, saved by upsert (task T034, FR-016, FR-017, R11)."""

import pytest
from conftest import make_user
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.profile.models import TaxpayerProfile
from app.profile.service import get_profile, save_profile

pytestmark = pytest.mark.anyio


async def test_no_profile_until_saved(db: AsyncSession) -> None:
    """Fails if a user appears to have a profile they never set up."""
    user = await make_user(db, "demo@example.com")

    assert await get_profile(db, user) is None


async def test_first_save_creates_and_second_replaces(db: AsyncSession) -> None:
    """Fails if saving doesn't store the answers, or a later save doesn't replace them."""
    user = await make_user(db, "demo@example.com")

    await save_profile(db, user, "2025-26", on_atl=False)
    await save_profile(db, user, "2025-26", on_atl=True)

    profile = await get_profile(db, user)
    assert profile is not None
    assert (profile.tax_year, profile.on_atl) == ("2025-26", True)
    count = (await db.execute(select(func.count()).select_from(TaxpayerProfile))).scalar_one()
    assert count == 1


async def test_unsupported_tax_year_is_refused(db: AsyncSession) -> None:
    """Fails if a tax year without FBR rates can be chosen (FR-017)."""
    user = await make_user(db, "demo@example.com")

    with pytest.raises(ValueError, match="Tax year 2024-25 is not supported."):
        await save_profile(db, user, "2024-25", on_atl=True)

    assert await get_profile(db, user) is None
