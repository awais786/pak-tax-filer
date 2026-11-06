"""Login throttling (T012, FR-007, research R4): 10 failures in 15 minutes block the 11th try."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginFailure, Session, User
from app.auth.passwords import hash_password

pytestmark = pytest.mark.anyio

EMAIL = "demo@example.com"
PASSWORD = "s3cret-pass"
TOO_MANY = {"detail": "Too many attempts. Try again later."}


@pytest.fixture
async def user(db: AsyncSession) -> User:
    """A demo user with a known password."""
    demo = User(email=EMAIL, password_hash=hash_password(PASSWORD))
    db.add(demo)
    await db.flush()
    return demo


async def fail_ten_times(client: AsyncClient, email: str) -> None:
    """Ten wrong-password attempts, each a 401."""
    for _ in range(10):
        response = await client.post(
            "/api/auth/login", json={"email": email, "password": "wrong-pass"}
        )
        assert response.status_code == 401


@pytest.mark.usefixtures("user")
async def test_eleventh_attempt_is_refused_even_with_the_right_password(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if guessing isn't slowed down, or a throttled attempt still logs in."""
    await fail_ten_times(client, EMAIL)

    response = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 429
    assert response.json() == TOO_MANY
    assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 0


@pytest.mark.usefixtures("user")
async def test_unknown_and_known_emails_are_throttled_the_same_way(client: AsyncClient) -> None:
    """Fails if throttling reveals which emails are registered."""
    await fail_ten_times(client, EMAIL)
    await fail_ten_times(client, "nobody@example.com")

    known = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json() == TOO_MANY


@pytest.mark.usefixtures("user")
async def test_failures_older_than_15_minutes_do_not_count(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if old failures keep an account locked (there is no permanent lockout)."""
    long_ago = datetime.now(UTC) - timedelta(minutes=16)
    db.add_all([LoginFailure(email=EMAIL, attempted_at=long_ago) for _ in range(10)])
    await db.flush()

    response = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 200
