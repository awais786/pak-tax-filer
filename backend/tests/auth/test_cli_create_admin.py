"""create-admin (feature 011, task T008; FR-001; contracts/admin-pages.md, "Command line").

An admin account is created only from the command line, always as a new account: an existing
email (any letter case) is refused, so a taxpayer account is never turned into an admin.
"""

import io
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.auth.models import User
from app.auth.passwords import verify_password
from app.cli import create_admin_command, create_user_command

pytestmark = pytest.mark.anyio


def prompts(*answers: str) -> Callable[[str], str]:
    """A stand-in for getpass that returns the given answers in order."""
    remaining = list(answers)
    return lambda _label: remaining.pop(0)


async def test_creates_an_admin_account(db: AsyncSession) -> None:
    """Fails if the account isn't an admin, the email isn't normalised, or the password isn't a
    usable hash."""
    out = io.StringIO()

    code = await create_admin_command(
        db, " Admin@Example.com ", prompts("admin-s3cret-pass", "admin-s3cret-pass"), out
    )

    assert code == 0
    assert out.getvalue().strip() == "Created admin admin@example.com"
    admin = (await db.execute(select(User))).scalar_one()
    assert admin.email == "admin@example.com" and admin.is_admin is True
    assert verify_password("admin-s3cret-pass", admin.password_hash)


async def test_never_turns_an_existing_account_into_an_admin(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if create-admin promotes a taxpayer account (with its tax data) to an admin."""
    await create_user_command(
        db, "taxpayer@example.com", prompts("admin-s3cret-pass", "admin-s3cret-pass"), io.StringIO()
    )

    code = await create_admin_command(
        db, "TAXPAYER@example.com", prompts("other-admin-pass", "other-admin-pass"), io.StringIO()
    )

    assert code == 1
    assert "A user with that email already exists." in capsys.readouterr().err
    taxpayer = (await db.execute(select(User))).scalar_one()
    assert taxpayer.is_admin is False


async def test_mismatched_passwords_create_nothing(db: AsyncSession) -> None:
    """Fails if a typo in the second password still creates an admin."""
    code = await create_admin_command(
        db, "admin@example.com", prompts("admin-s3cret-pass", "admin-s3cret-past"), io.StringIO()
    )

    assert code == 1
    assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0


def test_the_command_is_on_the_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails if `python -m app.cli create-admin --email …` doesn't reach create_admin_command."""
    called: dict[str, str] = {}

    async def fake_command(_db: object, email: str, _prompt: object, _out: object) -> int:
        called["email"] = email
        return 0

    async def fake_session(command: Callable[[object], Awaitable[int]]) -> int:
        return await command(None)

    monkeypatch.setattr(cli, "create_admin_command", fake_command)
    monkeypatch.setattr(cli, "_in_session", fake_session)

    assert cli.main(["create-admin", "--email", "admin@example.com"]) == 0
    assert called == {"email": "admin@example.com"}


async def test_an_admin_password_needs_at_least_12_characters(
    db: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if an internet-facing admin account can have a short password (review L5; the
    taxpayer minimum of 8 stays)."""
    code = await create_admin_command(
        db, "admin@example.com", prompts("elevenchars", "elevenchars"), io.StringIO()
    )

    assert code == 1
    assert "at least 12 characters" in capsys.readouterr().err
    assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0
    assert (
        await create_admin_command(
            db, "admin@example.com", prompts("twelve-chars", "twelve-chars"), io.StringIO()
        )
        == 0
    )
