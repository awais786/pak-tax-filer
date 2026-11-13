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

# Telemetry stays quiet in tests unless a test collects spans itself (feature 008): set before
# the app and its settings are imported.
os.environ.setdefault("OTEL_EXPORTER", "none")

# pylint: disable=wrong-import-position
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from document_helpers import PROFILE_YEAR, SALARY_RESULT
from rag_helpers import sessions_of
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from telemetry_helpers import CollectingExporter, Spans

from app.auth.models import User
from app.auth.passwords import hash_password
from app.db import get_db
from app.documents.extraction.client import FakeExtractor, failed
from app.documents.storage import Storage
from app.documents.router import get_extractor, get_storage
from app.main import app
from app.profile.service import save_profile
from app.rag.answer import AnswerError, FakeAnswerer
from app.rag.embed import FakeEmbedder
from app.rag.router import get_answerer, get_embedder
from app.telemetry.setup import add_exporter, instrument_engine
from app.workflow.client import FakeAgentClient
from app.workflow.router import get_agent_client, get_tool_sessions
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser
from app.wealth.router import get_wealth_summariser

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
    # Database spans as app.db's engine records them, for the telemetry tests (feature 008).
    engine = instrument_engine(create_async_engine(test_database_url, poolclass=NullPool))
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
        # As in production, a request that fails loses what it didn't commit (here: back to its
        # last savepoint), so tests can't pass on flushed-but-uncommitted rows (002 review M1).
        try:
            yield db
        except Exception:
            await db.rollback()
            raise

    app.dependency_overrides[get_db] = _test_db
    # 007's agent tools open their own sessions; in tests they get this one too.
    app.dependency_overrides[get_tool_sessions] = lambda: sessions_of(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
            yield http
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_tool_sessions, None)


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


# Feature 003: documents.


@pytest.fixture(autouse=True)
def no_real_ai() -> Iterator[None]:
    """Fakes for every AI service (and the guided run's agents) in every test, so no test can
    call the real Gemini API, even when the environment has a key (research R8 of 003). Tests
    wanting a particular answer override these again (fake_extractor, their own FakeSummariser
    or FakeAgentClient)."""
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(failed("No AI in tests."))
    app.dependency_overrides[get_summariser] = lambda: FakeSummariser(None)
    app.dependency_overrides[get_wealth_summariser] = lambda: FakeSummariser(None)
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_answerer] = lambda: FakeAnswerer(AnswerError("No AI in tests."))
    # A function, not the class: FastAPI would read the dataclass's fields as parameters.
    app.dependency_overrides[get_agent_client] = lambda: FakeAgentClient({})  # every agent fails
    yield
    app.dependency_overrides.pop(get_extractor, None)
    app.dependency_overrides.pop(get_summariser, None)
    app.dependency_overrides.pop(get_wealth_summariser, None)
    app.dependency_overrides.pop(get_embedder, None)
    app.dependency_overrides.pop(get_answerer, None)
    app.dependency_overrides.pop(get_agent_client, None)


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path) -> Iterator[Path]:
    """A temporary UPLOAD_DIR for every test, so no test ever writes to the real uploads
    volume (development data), even one that forgets to ask for this fixture."""
    app.dependency_overrides[get_storage] = lambda: Storage(tmp_path)
    yield tmp_path
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture
def fake_extractor() -> Iterator[FakeExtractor]:
    """The app's extractor, replaced by a fake returning SALARY_RESULT (change .result to vary)."""
    fake = FakeExtractor(SALARY_RESULT)
    app.dependency_overrides[get_extractor] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_extractor, None)


@pytest.fixture
async def user_with_profile(logged_in_user: User, db: AsyncSession) -> User:
    """The logged-in demo user, with a 2025-26 profile."""
    await save_profile(db, logged_in_user, PROFILE_YEAR, on_atl=True)
    return logged_in_user


@pytest.fixture(scope="session")
def memory_exporter() -> CollectingExporter:
    """One in-memory span exporter for the whole run, added through the app's own add_exporter
    so spans pass the same filter as the logs' (feature 008; a provider can't drop one)."""
    exporter = CollectingExporter()
    add_exporter(exporter, batch=False)
    return exporter


@pytest.fixture
def spans(memory_exporter: CollectingExporter) -> Iterator[Spans]:
    """The spans this test finishes (feature 008's telemetry tests)."""
    memory_exporter.clear()
    memory_exporter.collecting = True
    yield Spans(memory_exporter)
    memory_exporter.collecting = False
    memory_exporter.clear()
