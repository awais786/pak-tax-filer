"""Developer commands (feature 002, T016; feature 006, T028; feature 011, T009):

    python -m app.cli create-user --email <email>
    python -m app.cli create-admin --email <email>
    python -m app.cli create-token --email <email> [--name "Claude Code"]
    python -m app.cli revoke-token --prefix ptx_ab12

The password is typed twice at a hidden prompt, so it never lands in shell history (research R7
of 002). A token is printed once and only its SHA-256 is stored (006 research R8); there is no
token page or API (006 FR-016 amended). Contracts: specs/002-auth-foundation/contracts/
cli-and-ui.md and specs/006-rag-mcp/contracts/ask-and-tokens-api.md.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Coroutine, Sequence
from typing import Any, TextIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import create_user, get_user_by_email, normalize_email
from app.db import get_sessionmaker
from app.tokens.service import TOKEN_DAYS, create_token, revoke_token

DEFAULT_TOKEN_NAME = "MCP client"
# The admin area is on the open internet, so admins need longer passwords than taxpayers'
# 8 (feature 011, review L5).
ADMIN_MIN_PASSWORD = 12


async def create_user_command(
    db: AsyncSession, email: str, prompt: Callable[[str], str], out: TextIO
) -> int:
    """Create a demo user; return the exit code (0 created, 1 refused, nothing created)."""
    return await _create_account(db, email, prompt, out, admin=False)


async def create_admin_command(
    db: AsyncSession, email: str, prompt: Callable[[str], str], out: TextIO
) -> int:
    """Create a staff admin account (feature 011, FR-001): always a new account, so an existing
    email is refused and a taxpayer account is never promoted. 0 created, 1 refused."""
    return await _create_account(db, email, prompt, out, admin=True)


async def _create_account(
    db: AsyncSession, email: str, prompt: Callable[[str], str], out: TextIO, *, admin: bool
) -> int:
    password = prompt("Password: ")
    if prompt("Password again: ") != password:
        print("Passwords don't match; no user created.", file=sys.stderr)
        return 1
    if admin and len(password) < ADMIN_MIN_PASSWORD:
        print(
            f"Admin passwords must be at least {ADMIN_MIN_PASSWORD} characters; no user created.",
            file=sys.stderr,
        )
        return 1
    try:
        user = await create_user(db, email, password)
    except ValueError as error:
        print(f"{error} No user created.", file=sys.stderr)
        return 1
    user.is_admin = admin
    await db.commit()
    print(f"Created {'admin' if admin else 'user'} {normalize_email(email)}", file=out)
    return 0


async def create_token_command(
    db: AsyncSession, email: str, name: str, *, out: TextIO, err: TextIO
) -> int:
    """Create a token for a user and print it once; 0 created, 1 refused (nothing created)."""
    user = await get_user_by_email(db, email)
    if user is None:
        print(f"No user {normalize_email(email)}; no token created.", file=err)
        return 1
    if not user.can_use_app:  # an admin's or a disabled account's token would never work
        print(f"{user.email} can't use the app (admin or disabled); no token created.", file=err)
        return 1
    try:
        token = await create_token(db, user.id, name)
    except ValueError as error:
        print(f"{error} No token created.", file=err)
        return 1
    await db.commit()
    print(
        f"Token for {user.email} (valid {TOKEN_DAYS} days). It is shown only now; keep it in "
        f"your own environment as PAKTAX_TOKEN, never in a committed file:\n{token}",
        file=out,
    )
    return 0


async def revoke_token_command(db: AsyncSession, prefix: str, *, out: TextIO, err: TextIO) -> int:
    """Revoke the active token with this prefix; 0 revoked, 1 none (or several) found."""
    if not await revoke_token(db, prefix):
        print(f"No active token starts with {prefix!r}; nothing revoked.", file=err)
        return 1
    await db.commit()
    print(f"Revoked {prefix}.", file=out)
    return 0


async def _in_session(command: Callable[[AsyncSession], Coroutine[Any, Any, int]]) -> int:
    async with get_sessionmaker()() as db:
        return await command(db)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run the chosen command."""
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create a demo user (prompts for a password)")
    create.add_argument("--email", required=True)
    admin = commands.add_parser(
        "create-admin", help="create a new staff admin account (prompts for a password)"
    )
    admin.add_argument("--email", required=True)
    token = commands.add_parser("create-token", help="create an MCP token for a user")
    token.add_argument("--email", required=True)
    token.add_argument("--name", default=DEFAULT_TOKEN_NAME)
    revoke = commands.add_parser("revoke-token", help="revoke a token by its first 8 characters")
    revoke.add_argument("--prefix", required=True)
    args = parser.parse_args(argv)

    if args.command == "create-token":
        return asyncio.run(
            _in_session(
                lambda db: create_token_command(
                    db, args.email, args.name, out=sys.stdout, err=sys.stderr
                )
            )
        )
    if args.command == "create-admin":
        return asyncio.run(
            _in_session(
                lambda db: create_admin_command(db, args.email, getpass.getpass, sys.stdout)
            )
        )
    if args.command == "revoke-token":
        return asyncio.run(
            _in_session(
                lambda db: revoke_token_command(db, args.prefix, out=sys.stdout, err=sys.stderr)
            )
        )
    return asyncio.run(
        _in_session(lambda db: create_user_command(db, args.email, getpass.getpass, sys.stdout))
    )


if __name__ == "__main__":
    sys.exit(main())
