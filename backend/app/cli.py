"""Developer commands: `python -m app.cli create-user --email <email>` (feature 002, T016).

The password is typed twice at a hidden prompt, so it never lands in shell history (research R7).
Contract: specs/002-auth-foundation/contracts/cli-and-ui.md.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.users import create_user, normalize_email
from app.db import get_sessionmaker


async def create_user_command(
    db: AsyncSession, email: str, prompt: Callable[[str], str], out: TextIO
) -> int:
    """Create a demo user; return the exit code (0 created, 1 refused, nothing created)."""
    password = prompt("Password: ")
    if prompt("Password again: ") != password:
        print("Passwords don't match; no user created.", file=sys.stderr)
        return 1
    try:
        await create_user(db, email, password)
    except ValueError as error:
        print(f"{error} No user created.", file=sys.stderr)
        return 1
    await db.commit()
    print(f"Created user {normalize_email(email)}", file=out)
    return 0


async def _create_user_main(email: str) -> int:
    async with get_sessionmaker()() as db:
        return await create_user_command(db, email, getpass.getpass, sys.stdout)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run the chosen command."""
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create a demo user (prompts for a password)")
    create.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    return asyncio.run(_create_user_main(args.email))


if __name__ == "__main__":
    sys.exit(main())
