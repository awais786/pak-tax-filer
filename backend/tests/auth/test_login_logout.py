"""POST /api/auth/login and /logout, per specs/002-auth-foundation/contracts/auth-api.md (T011).

Logout is checked against the sessions table directly; GET /api/auth/me arrives with User
Story 2 and has its own tests.
"""

import hashlib
import logging

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User
from app.auth.passwords import hash_password
from app.auth import passwords
from app.auth import router as router_module
from app.auth.sessions import get_user_for_token
from app.settings import Settings

pytestmark = pytest.mark.anyio

EMAIL = "demo@example.com"
PASSWORD = "s3cret-pass"
INVALID = {"detail": "Invalid email or password."}


@pytest.fixture
async def user(db: AsyncSession) -> User:
    """A demo user with a known password."""
    demo = User(email=EMAIL, password_hash=hash_password(PASSWORD))
    db.add(demo)
    await db.flush()
    return demo


async def login(client: AsyncClient, email: str, password: str) -> Response:
    """POST a JSON login."""
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def session_count(db: AsyncSession) -> int:
    """How many sessions exist in the test transaction."""
    return (await db.execute(select(func.count()).select_from(Session))).scalar_one()


@pytest.mark.usefixtures("user")
async def test_login_sets_an_httponly_lax_cookie_and_stores_only_its_hash(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if login doesn't start a session, exposes the cookie to scripts, or stores the
    raw token."""
    response = await login(client, "  Demo@EXAMPLE.com ", PASSWORD)

    assert response.status_code == 200
    assert response.json() == {"email": EMAIL}
    set_cookie = response.headers["set-cookie"].lower()
    assert set_cookie.startswith("session=")
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    token = response.cookies["session"]
    stored = (await db.execute(select(Session))).scalar_one()
    assert stored.token_hash != token
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.usefixtures("user")
async def test_wrong_password_and_unknown_email_get_the_same_401(client: AsyncClient) -> None:
    """Fails if the response reveals whether an email is registered (FR-006)."""
    wrong_password = await login(client, EMAIL, "not-the-password")
    unknown_email = await login(client, "nobody@example.com", PASSWORD)

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == INVALID
    assert "session" not in wrong_password.cookies


@pytest.mark.usefixtures("user")
async def test_non_json_login_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if a form-encoded (cross-site style) request can log in (research R3)."""
    response = await client.post(
        "/api/auth/login",
        content=f"email={EMAIL}&password={PASSWORD}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 415
    assert await session_count(db) == 0


@pytest.mark.usefixtures("user")
async def test_logout_ends_the_session_and_clears_the_cookie(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if a logged-out session still works or its row survives (FR-008)."""
    token = (await login(client, EMAIL, PASSWORD)).cookies["session"]

    response = await client.post("/api/auth/logout", json={})

    assert response.status_code == 204
    assert (
        'session=""' in response.headers["set-cookie"]
        or "max-age=0" in response.headers["set-cookie"].lower()
    )
    assert await session_count(db) == 0
    assert await get_user_for_token(db, token) is None


@pytest.mark.usefixtures("user")
async def test_two_logins_are_independent_sessions(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if logging out on one device logs out the other."""
    first = (await login(client, EMAIL, PASSWORD)).cookies["session"]
    client.cookies.clear()
    second = (await login(client, EMAIL, PASSWORD)).cookies["session"]

    # Log out the first device only: replace the jar's cookie with the first token.
    client.cookies.clear()
    client.cookies.set("session", first)
    await client.post("/api/auth/logout", json={})

    assert first != second
    assert await get_user_for_token(db, first) is None
    still_logged_in = await get_user_for_token(db, second)
    assert still_logged_in is not None and still_logged_in.email == EMAIL


@pytest.mark.usefixtures("user")
async def test_passwords_and_tokens_never_reach_the_logs(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Fails if any logger (ours or a library's, at any level) records a password or a session
    token during a successful or failed login (FR-003; security rules)."""
    caplog.set_level(logging.DEBUG)

    token = (await login(client, EMAIL, PASSWORD)).cookies["session"]
    await login(client, EMAIL, "wrong-password-typed")

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in (PASSWORD, "wrong-password-typed", token):
        assert secret not in logged


@pytest.mark.usefixtures("user")
async def test_unknown_email_pays_for_the_same_password_check(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if an unknown email skips the Argon2 check, which would make it faster and so
    reveal which emails exist (research R5)."""
    checked: list[str] = []
    real_verify = passwords.verify_password

    def spy(password: str, password_hash: str) -> bool:
        checked.append(password_hash)
        return real_verify(password, password_hash)

    monkeypatch.setattr(passwords, "verify_password", spy)

    await login(client, "nobody@example.com", PASSWORD)

    assert checked == [passwords.DUMMY_HASH]


@pytest.mark.usefixtures("user")
async def test_cookie_is_secure_with_a_seven_day_lifetime_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if the session cookie drops Secure, Max-Age or Path (research R2)."""
    monkeypatch.setattr(
        router_module, "get_settings", lambda: Settings(database_url="unused", cookie_secure=True)
    )

    login_cookie = (await login(client, EMAIL, PASSWORD)).headers["set-cookie"].lower()
    logout_cookie = (await client.post("/api/auth/logout", json={})).headers["set-cookie"].lower()

    for part in ("secure", "max-age=604800", "path=/", "httponly", "samesite=lax"):
        assert part in login_cookie
    for part in ("secure", "path=/"):
        assert part in logout_cookie


@pytest.mark.parametrize(
    "body",
    [
        {"email": "x" * 250 + "@example.com", "password": PASSWORD},
        {"email": EMAIL, "password": "p" * 1025},
        {"email": "", "password": PASSWORD},
        {"email": EMAIL, "password": ""},
    ],
    ids=["email-too-long", "password-too-long", "email-empty", "password-empty"],
)
async def test_unreasonable_login_fields_are_refused(
    client: AsyncClient, body: dict[str, str]
) -> None:
    """Fails if huge or empty values are accepted (and, for huge ones, hashed and stored)."""
    response = await client.post("/api/auth/login", json=body)

    assert response.status_code == 422


@pytest.mark.usefixtures("user")
async def test_non_json_logout_is_refused_and_the_session_survives(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if a cross-site form could log a user out (research R3)."""
    await login(client, EMAIL, PASSWORD)

    response = await client.post(
        "/api/auth/logout", content="", headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 415
    assert await session_count(db) == 1


def cookie_settings(set_cookie: str) -> set[str]:
    """A Set-Cookie header's settings (path, flags, SameSite), without its value or lifetime."""
    parts = [part.strip().lower() for part in set_cookie.split(";")[1:]]
    return {part for part in parts if not part.startswith(("max-age", "expires"))}


@pytest.mark.usefixtures("user")
async def test_logout_clears_the_cookie_with_the_same_settings_it_was_set_with(
    client: AsyncClient,
) -> None:
    """Fails if login and logout drift apart: a browser only clears a cookie whose path and
    flags match the one it holds (review of PR #27, item 10)."""
    set_on_login = (await login(client, EMAIL, PASSWORD)).headers["set-cookie"]

    cleared_on_logout = (await client.post("/api/auth/logout", json={})).headers["set-cookie"]

    assert cookie_settings(cleared_on_logout) == cookie_settings(set_on_login)
