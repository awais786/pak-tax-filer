"""GET/PUT /api/profile, per specs/002-auth-foundation/contracts/auth-api.md (task T035).

FR-016 to FR-018, FR-021 to FR-023.
"""

import pytest
from conftest import TEST_PASSWORD, make_user
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User
from app.profile.service import get_profile

pytestmark = pytest.mark.anyio

NOT_LOGGED_IN = {"detail": "Not logged in."}


async def test_logged_out_requests_are_refused(client: AsyncClient) -> None:
    """Fails if anyone not logged in can read or change a profile."""
    read = await client.get("/api/profile")
    write = await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": True})

    assert read.status_code == write.status_code == 401
    assert read.json() == write.json() == NOT_LOGGED_IN


@pytest.mark.usefixtures("logged_in_user")
async def test_no_profile_yet_is_a_normal_answer(client: AsyncClient) -> None:
    """Fails if 'no profile' is an error, or the supported years aren't offered (R13)."""
    response = await client.get("/api/profile")

    assert response.status_code == 200
    assert response.json() == {"profile": None, "supported_tax_years": ["2025-26"]}


@pytest.mark.usefixtures("logged_in_user")
async def test_saved_profile_is_returned(client: AsyncClient) -> None:
    """Fails if a saved profile isn't stored and read back with its answers."""
    saved = await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": False})
    read = await client.get("/api/profile")

    assert saved.status_code == 200
    assert saved.json()["tax_year"] == "2025-26"
    assert saved.json()["on_atl"] is False
    assert set(saved.json()) == {"tax_year", "on_atl", "updated_at"}
    assert read.json()["profile"] == saved.json()


@pytest.mark.usefixtures("logged_in_user")
async def test_unsupported_tax_year_is_refused(client: AsyncClient) -> None:
    """Fails if a tax year without FBR rates can be saved (FR-017)."""
    response = await client.put("/api/profile", json={"tax_year": "2024-25", "on_atl": True})

    assert response.status_code == 422
    assert response.json() == {"detail": "Tax year 2024-25 is not supported."}


@pytest.mark.usefixtures("logged_in_user")
@pytest.mark.parametrize(
    "body",
    [
        {"tax_year": "2025-26"},
        {"tax_year": "2025-26", "on_atl": "yes"},
        {"tax_year": "2025-26", "on_atl": None},
        {"tax_year": "2025-26", "on_atl": True, "cnic": "00000-0000000-0"},
    ],
    ids=["atl-missing", "atl-not-boolean", "atl-unknown", "identity-field"],
)
async def test_invalid_answers_and_extra_fields_are_refused(
    client: AsyncClient, body: dict[str, object]
) -> None:
    """Fails if ATL can be left unanswered (FR-016) or identity data stored (FR-018)."""
    response = await client.put("/api/profile", json=body)

    assert response.status_code == 422


async def test_one_users_save_never_touches_anothers_profile(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a profile is visible or changeable by another account (FR-023)."""
    await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": True})
    other = await make_user(db, "other@example.com")
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": other.email, "password": TEST_PASSWORD})

    others_view = await client.get("/api/profile")
    await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": False})
    client.cookies.clear()
    await client.post(
        "/api/auth/login", json={"email": logged_in_user.email, "password": TEST_PASSWORD}
    )

    assert others_view.json()["profile"] is None
    assert (await client.get("/api/profile")).json()["profile"]["on_atl"] is True


async def test_changing_the_profile_updates_it_and_nothing_else(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a change doesn't replace the answer and update the time, or touches anything
    else the user has saved (FR-021, SC-009)."""
    first = (await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": True})).json()
    sessions_before = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
    before = await get_profile(db, logged_in_user)
    assert before is not None
    created_before = before.created_at

    second = (
        await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": False})
    ).json()

    assert second["on_atl"] is False
    assert second["updated_at"] > first["updated_at"]
    after = await get_profile(db, logged_in_user)
    assert after is not None and after.created_at == created_before
    sessions_after = (await db.execute(select(func.count()).select_from(Session))).scalar_one()
    assert sessions_after == sessions_before


@pytest.mark.usefixtures("logged_in_user")
async def test_non_json_profile_save_is_refused(client: AsyncClient) -> None:
    """Fails if a cross-site form could change the profile (research R3)."""
    response = await client.put(
        "/api/profile",
        content="tax_year=2025-26&on_atl=true",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 415
