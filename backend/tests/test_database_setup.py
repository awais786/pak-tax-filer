"""The test-database fixtures in conftest.py (feature 002, task T008, research R10).

These need PostgreSQL: run them with `docker compose exec backend pytest` (or in CI).
"""

import pytest
from httpx2 import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User

pytestmark = pytest.mark.anyio


async def test_runs_against_the_test_database_with_migrations_applied(db: AsyncSession) -> None:
    """Fails if tests use the development database or the migrations weren't applied."""
    name = (await db.execute(text("select current_database()"))).scalar_one()
    tables = set(
        (await db.execute(text("select tablename from pg_tables where schemaname = 'public'")))
        .scalars()
        .all()
    )

    assert name == "pak_tax_filer_test"
    assert {"users", "sessions", "login_failures"} <= tables


@pytest.mark.parametrize("attempt", [1, 2])
async def test_each_test_is_rolled_back(db: AsyncSession, attempt: int) -> None:
    """Fails if one test's rows leak into the next: the second insert of the same unique email
    would then violate users.email's unique constraint."""
    db.add(User(email="isolation@example.com", password_hash="not-a-real-hash"))
    await db.flush()

    count = (
        await db.execute(text("select count(*) from users where email = 'isolation@example.com'"))
    ).scalar_one()
    assert count == 1, f"attempt {attempt} saw rows from another test"


async def test_client_reaches_the_app(client: AsyncClient) -> None:
    """Fails if the HTTP client fixture isn't wired to the FastAPI app."""
    response = await client.get("/health")

    assert response.status_code == 200
