"""Admin accounts are staff-only, and disabled accounts are refused (feature 011, task T006;
FR-002, FR-014a; contracts/admin-pages.md, "Effect on the taxpayer app").

The taxpayer app answers an admin or a disabled account exactly as it answers a wrong password
or no session, so nothing tells an outsider which accounts are which.
"""

import io
from datetime import UTC, datetime, timedelta

import pytest
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User
from app.auth.passwords import hash_password
from app.auth.sessions import SESSION_LIFETIME, create_session
from app.cli import create_token_command
from app.tokens.service import create_token, owner_of

pytestmark = pytest.mark.anyio

PASSWORD = "s3cret-pass"
INVALID = {"detail": "Invalid email or password."}
NOT_LOGGED_IN = {"detail": "Not logged in."}


async def account(
    db: AsyncSession, email: str, *, admin: bool = False, disabled: bool = False
) -> User:
    """A synthetic account with a known password."""
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        is_admin=admin,
        disabled_at=datetime.now(UTC) if disabled else None,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.parametrize(("admin", "disabled"), [(True, False), (False, True)])
async def test_the_app_login_refuses_admin_and_disabled_accounts(
    client: AsyncClient, db: AsyncSession, admin: bool, disabled: bool
) -> None:
    """Fails if an admin can sign in to the taxpayer app, or a disabled account can sign in, or
    either gets a different answer from a wrong password."""
    await account(db, "someone@example.com", admin=admin, disabled=disabled)

    response = await client.post(
        "/api/auth/login", json={"email": "someone@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401 and response.json() == INVALID
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(("admin", "disabled"), [(True, False), (False, True)])
async def test_a_session_of_an_admin_or_disabled_account_is_not_logged_in(
    client: AsyncClient, db: AsyncSession, admin: bool, disabled: bool
) -> None:
    """Fails if a session that already exists (an admin's, or one made before the account was
    disabled) opens any taxpayer endpoint."""
    user = await account(db, "someone@example.com", admin=admin, disabled=disabled)
    token = await create_session(db, user)
    client.cookies.set("session", token)

    response = await client.get("/api/auth/me")

    assert response.status_code == 401 and response.json() == NOT_LOGGED_IN


@pytest.mark.parametrize(("admin", "disabled"), [(True, False), (False, True)])
async def test_an_access_token_of_an_admin_or_disabled_account_acts_for_nobody(
    db: AsyncSession, admin: bool, disabled: bool
) -> None:
    """Fails if the assistant's tools (MCP) accept a token of an admin or a disabled account."""
    user = await account(db, "someone@example.com", admin=admin, disabled=disabled)
    token = await create_token(db, user.id, "laptop")

    assert await owner_of(db, token) is None


async def test_an_active_taxpayer_still_signs_in(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if the new checks refuse an ordinary account."""
    await account(db, "taxpayer@example.com")

    response = await client.post(
        "/api/auth/login", json={"email": "taxpayer@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200


async def test_a_session_can_be_given_a_shorter_lifetime(db: AsyncSession) -> None:
    """Fails if the admin's 8-hour session can't be made, or the app's default changes."""
    user = await account(db, "someone@example.com")
    before = datetime.now(UTC)

    await create_session(db, user, lifetime=timedelta(hours=8))
    await create_session(db, user)

    short, default = (
        await db.scalars(select(Session.expires_at).order_by(Session.expires_at))
    ).all()
    assert timedelta(hours=7, minutes=59) < short - before <= timedelta(hours=8, seconds=5)
    assert SESSION_LIFETIME - timedelta(minutes=1) < default - before


@pytest.mark.parametrize(("admin", "disabled"), [(True, False), (False, True)])
async def test_create_token_refuses_admin_and_disabled_accounts(
    db: AsyncSession, admin: bool, disabled: bool
) -> None:
    """Fails if the command line makes a token that could never be used (review L6)."""
    await account(db, "someone@example.com", admin=admin, disabled=disabled)
    out, err = io.StringIO(), io.StringIO()

    code = await create_token_command(db, "someone@example.com", "laptop", out=out, err=err)

    assert code == 1 and out.getvalue() == ""
    assert "can't use the app" in err.getvalue()
