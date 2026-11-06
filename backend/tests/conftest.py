"""Test-database fixtures (feature 002, task T008, research R10).

Tests that ask for `db` or `client` run against a separate `pak_tax_filer_test` database in the
same PostgreSQL server as DATABASE_URL, never the development data. The database is created if
missing and migrated once per run; each test runs inside a transaction that is rolled back.
Tests that don't ask for these fixtures (e.g. /health, settings) need no database at all.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import User
from app.auth.passwords import hash_password
from app.db import get_db
from app.main import app

TEST_DATABASE = "pak_tax_filer_test"
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run async tests on asyncio (what FastAPI and asyncpg use)."""
    return "asyncio"


async def _create_database_if_missing(server_url: str) -> None:
    """CREATE DATABASE needs autocommit and a connection to another database."""
    engine = create_async_engine(server_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("select 1 from pg_database where datname = :name"), {"name": TEST_DATABASE}
            )
            if not exists:
                await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create and migrate the test database once per run; yield its URL."""
    server_url = os.environ.get("DATABASE_URL")
    if not server_url:
        pytest.fail(
            "DATABASE_URL is not set: database tests run in Docker "
            "(`docker compose exec backend pytest`) or CI."
        )
    url = make_url(server_url).set(database=TEST_DATABASE).render_as_string(hide_password=False)

    asyncio.run(_create_database_if_missing(server_url))

    # alembic/env.py reads DATABASE_URL, so point it at the test database while migrating.
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(Config(os.path.join(BACKEND_DIR, "alembic.ini")), "head")
    finally:
        os.environ["DATABASE_URL"] = server_url
    yield url


@pytest.fixture
async def db(test_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    connection = await engine.connect()
    transaction = await connection.begin()
    # Code under test may commit; savepoints keep those commits inside the outer transaction.
    # Same settings as app.db.get_sessionmaker (expire_on_commit=False), so tests behave like the
    # app: after a commit, objects keep their loaded values instead of reloading lazily.
    session = AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """An HTTP client for the app whose requests use the test's rolled-back session."""

    async def _test_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = _test_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
            yield http
    finally:
        app.dependency_overrides.pop(get_db, None)


TEST_PASSWORD = "s3cret-pass"


async def make_user(db: AsyncSession, email: str) -> User:
    """A synthetic user whose password is TEST_PASSWORD."""
    user = User(email=email, password_hash=hash_password(TEST_PASSWORD))
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def logged_in_user(client: AsyncClient, db: AsyncSession) -> User:
    """A demo user, logged in on `client` (the client keeps the session cookie)."""
    user = await make_user(db, "demo@example.com")
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    return user
