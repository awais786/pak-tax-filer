"""create-user command, per specs/002-auth-foundation/contracts/cli-and-ui.md.

Task T010; FR-002, FR-004.
"""

import io
from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import verify_password
from app.auth import users
from app.cli import create_user_command

pytestmark = pytest.mark.anyio


def prompts(*answers: str) -> Callable[[str], str]:
    """A stand-in for getpass that returns the given answers in order."""
    remaining = list(answers)
    return lambda _label: remaining.pop(0)


async def user_count(db: AsyncSession) -> int:
    """How many users exist in the test transaction."""
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def test_creates_a_user_with_a_trimmed_lower_cased_email(db: AsyncSession) -> None:
    """Fails if the email isn't normalised or the password isn't stored as a usable hash."""
    out = io.StringIO()

    code = await create_user_command(
        db, "  Demo@Example.COM ", prompts("s3cret-pass", "s3cret-pass"), out
    )

    assert code == 0
    assert out.getvalue().strip() == "Created user demo@example.com"
    user = (await db.execute(select(User))).scalar_one()
    assert user.email == "demo@example.com"
    assert verify_password("s3cret-pass", user.password_hash)


async def test_refuses_an_existing_email_in_another_letter_case(db: AsyncSession) -> None:
    """Fails if a duplicate account can be created by changing letter case."""
    await create_user_command(
        db, "demo@example.com", prompts("s3cret-pass", "s3cret-pass"), io.StringIO()
    )

    code = await create_user_command(
        db, "DEMO@example.com", prompts("other-pass1", "other-pass1"), io.StringIO()
    )

    assert code == 1
    assert await user_count(db) == 1


@pytest.mark.parametrize(
    ("first", "second"),
    [("short7c", "short7c"), ("s3cret-pass", "s3cret-pasS")],
    ids=["under-8-characters", "confirmation-mismatch"],
)
async def test_refuses_bad_passwords_and_creates_nothing(
    db: AsyncSession, first: str, second: str
) -> None:
    """Fails if a short or mistyped password creates an account."""
    code = await create_user_command(db, "demo@example.com", prompts(first, second), io.StringIO())

    assert code == 1
    assert await user_count(db) == 0


async def test_a_race_on_the_same_email_is_refused_cleanly(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if two create-user runs racing on one email crash instead of refusing: the
    existence check passes for both, and the database's unique email is the real guard."""
    await create_user_command(
        db, "demo@example.com", prompts("s3cret-pass", "s3cret-pass"), io.StringIO()
    )

    async def never_found(_db: AsyncSession, _email: str) -> None:
        return None

    monkeypatch.setattr(users, "get_user_by_email", never_found)

    code = await create_user_command(
        db, "demo@example.com", prompts("other-pass1", "other-pass1"), io.StringIO()
    )

    assert code == 1
    assert await user_count(db) == 1
