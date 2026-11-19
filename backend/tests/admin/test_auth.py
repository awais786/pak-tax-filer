"""Signing in to the admin area (feature 011, task T012; FR-003 to FR-005; research R2;
contracts/admin-pages.md, "Access")."""

from datetime import UTC, datetime, timedelta

import pytest
from admin_helpers import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    INVALID,
    admin_client,
    csrf_token,
    make_admin,
    sign_in,
)
from conftest import TEST_PASSWORD, make_user
from httpx2 import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import auth as auth_module
from app.auth.models import LoginFailure, Session, User
from app.auth.sessions import create_session
from app.settings import Settings

pytestmark = pytest.mark.anyio


async def test_not_signed_in_goes_to_the_login_page(db: AsyncSession) -> None:
    """Fails if any admin page opens without signing in."""
    async with admin_client(db) as http:
        response = await http.get("/admin/")

    assert response.status_code in (302, 303, 307)
    assert "/admin/login" in response.headers["location"]


@pytest.mark.parametrize("secure", [True, False])
async def test_an_admin_signs_in_with_the_admin_cookie(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, secure: bool
) -> None:
    """Fails if the cookie isn't HttpOnly, SameSite=Strict, scoped to /admin and 8 hours, and
    Secure unless COOKIE_SECURE is off (FR-005), or the dashboard doesn't open afterwards."""
    monkeypatch.setattr(
        auth_module, "get_settings", lambda: Settings(database_url="unused", cookie_secure=secure)
    )
    await make_admin(db)

    async with admin_client(db) as http:
        response = await sign_in(http)
        dashboard = await http.get("/admin/")

    cookie = response.headers["set-cookie"]
    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin/")  # the dashboard, not another page
    assert cookie.startswith("admin_session=")
    for part in ("HttpOnly", "SameSite=strict", "Path=/admin", "Max-Age=28800"):
        assert part.lower() in cookie.lower(), part
    assert ("secure" in cookie.lower().split("; ")) is secure
    assert dashboard.status_code == 200


@pytest.mark.parametrize("case", ["taxpayer", "wrong_password", "disabled", "unknown"])
async def test_everyone_else_gets_one_generic_refusal(db: AsyncSession, case: str) -> None:
    """Fails if a taxpayer, a wrong password, a disabled admin or an unknown email is let in, or
    gets a message that tells them apart (FR-003)."""
    await make_admin(db)
    await make_user(db, "taxpayer@example.com")
    if case == "disabled":
        await db.execute(
            update(User).where(User.email == ADMIN_EMAIL).values(disabled_at=datetime.now(UTC))
        )
    email, password = {
        "taxpayer": ("taxpayer@example.com", TEST_PASSWORD),
        "wrong_password": (ADMIN_EMAIL, "not-the-password"),
        "disabled": (ADMIN_EMAIL, ADMIN_PASSWORD),
        "unknown": ("nobody@example.com", ADMIN_PASSWORD),
    }[case]

    async with admin_client(db) as http:
        response = await sign_in(http, email, password)

    assert response.status_code == 400
    assert INVALID in response.text
    assert "admin_session" not in response.headers.get("set-cookie", "")


async def test_failures_are_throttled_separately_from_the_app(
    db: AsyncSession, client: AsyncClient
) -> None:
    """Fails if 10 failures don't lock the admin sign-in for that email (FR-004), or if they are
    counted with the app's, so failing on the public login page could lock an admin out."""
    await make_admin(db)
    async with admin_client(db) as http:
        for _ in range(10):
            await sign_in(http, ADMIN_EMAIL, "not-the-password")
        locked = await sign_in(http)

    assert locked.status_code == 400 and "Too many attempts. Try again later." in locked.text
    stored = (await db.scalars(select(LoginFailure.email).distinct())).all()
    assert stored == [f"{auth_module.THROTTLE_PREFIX}{ADMIN_EMAIL}"]
    taxpayer = await make_user(db, "demo@example.com")
    app_login = await client.post(
        "/api/auth/login", json={"email": taxpayer.email, "password": TEST_PASSWORD}
    )
    assert app_login.status_code == 200


async def test_an_app_session_cookie_does_not_open_the_admin_area(db: AsyncSession) -> None:
    """Fails if the taxpayer app's cookie (even an admin's session under that name) opens /admin."""
    admin = await make_admin(db)
    token = await create_session(db, admin)

    async with admin_client(db) as http:
        http.cookies.set("session", token)
        response = await http.get("/admin/")

    assert "/admin/login" in response.headers.get("location", "")


async def test_an_expired_admin_session_does_not_open_it(db: AsyncSession) -> None:
    """Fails if an admin session works after its 8 hours."""
    await make_admin(db)
    async with admin_client(db) as http:
        await sign_in(http)
        await db.execute(
            update(Session).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        response = await http.get("/admin/")

    assert "/admin/login" in response.headers.get("location", "")


async def test_signing_out_ends_the_session(db: AsyncSession) -> None:
    """Fails if signing out leaves the session usable or the cookie set."""
    await make_admin(db)
    async with admin_client(db) as http:
        await sign_in(http)
        page = await http.get("/admin/")
        response = await http.post("/admin/logout", data={"csrftoken": csrf_token(page.text)})
        after = await http.get("/admin/")

    assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 0
    assert 'admin_session=""' in response.headers.get("set-cookie", "") or "Max-Age=0" in (
        response.headers.get("set-cookie", "")
    )
    assert "/admin/login" in after.headers.get("location", "")


def test_the_app_serves_the_admin_area_at_admin() -> None:
    """Fails if the real app doesn't mount the admin area at /admin (FR-025)."""
    from app.main import app  # pylint: disable=import-outside-toplevel

    assert "/admin" in [getattr(route, "path", None) for route in app.routes]


async def test_failures_on_the_public_login_never_reach_the_admin_throttle(
    db: AsyncSession, client: AsyncClient
) -> None:
    """Fails if 10 failed public logins for "admin:" + an admin's email lock the admin out of
    /admin (review M3: the two throttles must not share a key)."""
    await make_admin(db)
    for _ in range(10):
        await client.post(
            "/api/auth/login", json={"email": f"admin:{ADMIN_EMAIL}", "password": "wrong-pass"}
        )

    async with admin_client(db) as http:
        response = await sign_in(http)

    assert response.status_code == 303


@pytest.mark.parametrize(
    ("email", "password"),
    [("a" * 250 + "@example.com", ADMIN_PASSWORD), (ADMIN_EMAIL, "p" * 1025)],
)
async def test_oversized_sign_ins_are_refused_without_storing_anything(
    db: AsyncSession, email: str, password: str
) -> None:
    """Fails if the admin login accepts any length (the public login caps 254/1024) or stores a
    failure for it, which would let anyone fill the disk (review M2)."""
    await make_admin(db)

    async with admin_client(db) as http:
        response = await sign_in(http, email, password)

    assert response.status_code == 400 and INVALID in response.text
    assert (await db.execute(select(func.count()).select_from(LoginFailure))).scalar_one() == 0
