"""require_profile: later features refuse users without a profile (task T036, FR-022, R14).

The stand-in endpoint lives on a throwaway app, so the real app gains no test-only routes.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from conftest import TEST_PASSWORD, make_user
from fastapi import Depends, FastAPI
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import router as auth_router
from app.db import get_db
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.profile.router import router as profile_router

pytestmark = pytest.mark.anyio


@pytest.fixture
async def feature_client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """A throwaway app with login, the profile API and one endpoint that needs a profile."""
    feature = FastAPI()
    feature.include_router(auth_router)
    feature.include_router(profile_router)

    @feature.get("/needs-profile")
    async def needs_profile(
        profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    ) -> dict[str, str]:
        return {"tax_year": profile.tax_year}

    async def _test_db() -> AsyncIterator[AsyncSession]:
        yield db

    feature.dependency_overrides[get_db] = _test_db
    user = await make_user(db, "demo@example.com")
    async with AsyncClient(transport=ASGITransport(app=feature), base_url="https://test") as http:
        await http.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        yield http


async def test_without_a_profile_the_request_is_refused(feature_client: AsyncClient) -> None:
    """Fails if a feature that needs the profile can run without one."""
    response = await feature_client.get("/needs-profile")

    assert response.status_code == 409
    assert response.json() == {"detail": "Set up your profile first."}


async def test_with_a_profile_the_endpoint_receives_it(feature_client: AsyncClient) -> None:
    """Fails if the saved profile isn't handed to the endpoint."""
    await feature_client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": True})

    response = await feature_client.get("/needs-profile")

    assert response.status_code == 200
    assert response.json() == {"tax_year": "2025-26"}
