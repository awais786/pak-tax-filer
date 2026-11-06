"""current_user protection via GET /api/auth/me (feature 002, task T019, FR-010, FR-011)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx2 import AsyncClient
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User
from app.auth.passwords import hash_password
from app.auth.sessions import get_user_for_token

pytestmark = pytest.mark.anyio

EMAIL = "demo@example.com"
PASSWORD = "s3cret-pass"
NOT_LOGGED_IN = {"detail": "Not logged in."}


@pytest.fixture
async def user(db: AsyncSession) -> User:
    """A demo user with a known password."""
    demo = User(email=EMAIL, password_hash=hash_password(PASSWORD))
    db.add(demo)
    await db.flush()
    return demo


async def log_in(client: AsyncClient) -> str:
    """Log in and return the session token (the client keeps the cookie)."""
    response = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    return response.cookies["session"]


async def test_me_without_a_cookie_is_refused(client: AsyncClient) -> None:
    """Fails if a protected endpoint answers anyone who isn't logged in."""
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_LOGGED_IN


async def test_me_with_an_unknown_token_is_refused(client: AsyncClient) -> None:
    """Fails if a made-up cookie value is accepted."""
    client.cookies.set("session", "made-up-token")

    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_LOGGED_IN


@pytest.mark.usefixtures("user")
async def test_me_after_logout_is_refused(client: AsyncClient) -> None:
    """Fails if a logged-out session still works (FR-008)."""
    token = await log_in(client)
    await client.post("/api/auth/logout", json={})
    client.cookies.set("session", token)

    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_LOGGED_IN


@pytest.mark.usefixtures("user")
async def test_me_with_an_expired_session_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if a session older than 7 days still works (FR-009)."""
    await log_in(client)
    await db.execute(update(Session).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))

    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == NOT_LOGGED_IN


@pytest.mark.usefixtures("user")
async def test_me_with_a_valid_session_returns_only_the_email(client: AsyncClient) -> None:
    """Fails if a valid session is refused, or /me reveals anything beyond the email (FR-011)."""
    await log_in(client)

    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {"email": EMAIL}


@pytest.mark.usefixtures("user")
async def test_expired_session_row_is_deleted_when_used(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if expired sessions pile up instead of being removed when next used (research R6)."""
    await log_in(client)
    await db.execute(update(Session).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))

    await client.get("/api/auth/me")

    assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 0


@pytest.mark.usefixtures("user")
async def test_a_protected_request_reads_the_session_and_user_in_one_query(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if checking a session takes more than one query (review of PR #27, item 8)."""
    token = await log_in(client)
    statements: list[str] = []

    def record(*args: object) -> None:
        statement = str(args[2])
        if not statement.startswith(("SAVEPOINT", "RELEASE SAVEPOINT")):  # the test harness's
            statements.append(statement)

    db.expunge_all()  # A real request starts with nothing cached.
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        found = await get_user_for_token(db, token)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert found is not None
    assert found.email == EMAIL
    assert len(statements) == 1, statements
