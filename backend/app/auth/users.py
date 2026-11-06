"""User lookup and creation, shared by the login endpoint and the create-user command."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password

MIN_PASSWORD_LENGTH = 8  # FR-002: at least 8 characters, no other composition rules


def normalize_email(email: str) -> str:
    """Emails are compared trimmed and lower-cased (FR-001)."""
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """The user with this email (any letter case or surrounding spaces), or None."""
    return (
        await db.execute(select(User).where(User.email == normalize_email(email)))
    ).scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    """Create a user; raises ValueError if the email is taken or the password too short."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if await get_user_by_email(db, email) is not None:
        raise ValueError("A user with that email already exists.")
    user = User(email=normalize_email(email), password_hash=hash_password(password))
    try:
        # A savepoint, so losing a race keeps the rest of the transaction usable.
        async with db.begin_nested():
            db.add(user)
    except IntegrityError as error:
        # Another run created the same email between the check above and this insert; the
        # database's unique constraint is the real guard (review L6).
        raise ValueError("A user with that email already exists.") from error
    return user
