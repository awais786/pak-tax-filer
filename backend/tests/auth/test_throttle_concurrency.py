"""Throttling holds under concurrent attempts (backend review M2, FR-007, research R4).

Unlike the other tests, each request here needs its own database connection so they can truly
run at the same time; rows are committed to the test database and removed afterwards.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from conftest import TEST_PASSWORD
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import LoginFailure, User
from app.auth.passwords import hash_password
from app.db import get_db
from app.main import app

pytestmark = pytest.mark.anyio

EMAIL = "race@example.com"


async def test_simultaneous_guesses_cannot_get_past_the_limit(test_database_url: str) -> None:
    """Fails if attempts sent at the same moment all read the failure count before any of them
    records a failure, so many more than 10 guesses get checked in 15 minutes."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def separate_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    async with sessions() as setup:
        setup.add(User(email=EMAIL, password_hash=hash_password(TEST_PASSWORD)))
        setup.add_all([LoginFailure(email=EMAIL) for _ in range(9)])  # one short of the limit
        await setup.commit()

    app.dependency_overrides[get_db] = separate_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
            responses = await asyncio.gather(
                *(
                    http.post("/api/auth/login", json={"email": EMAIL, "password": "wrong-pass-1"})
                    for _ in range(15)
                )
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with sessions() as cleanup:
            await cleanup.execute(delete(LoginFailure).where(LoginFailure.email == EMAIL))
            await cleanup.execute(delete(User).where(User.email == EMAIL))
            await cleanup.commit()
        await engine.dispose()

    statuses = sorted(r.status_code for r in responses)
    # Only the tenth failure may be checked; every other attempt must be refused as throttled.
    assert statuses.count(401) == 1, statuses
    assert statuses.count(429) == 14, statuses
