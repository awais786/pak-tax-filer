"""Creating, revoking and checking personal access tokens (feature 006, task T028; research R8).

A token is "ptx_" plus 32 random bytes; only its SHA-256 is stored, as 002 stores session
tokens (random values need no slow hash, unlike passwords). The prefix makes a leaked token
recognisable to secret scanners and lets a developer revoke one by its first 8 characters.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.tokens.models import PersonalAccessToken

TOKEN_DAYS = 90
PREFIX_LENGTH = 8
MAX_NAME_LENGTH = 50


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_token(db: AsyncSession, user_id: uuid.UUID, name: str) -> str:
    """A new token for this user; the full value is returned once and never stored."""
    name = name.strip()
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise ValueError(f"A token's name must be 1 to {MAX_NAME_LENGTH} characters.")
    token = "ptx_" + secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        PersonalAccessToken(
            user_id=user_id,
            name=name,
            token_hash=_hash(token),
            prefix=token[:PREFIX_LENGTH],
            created_at=now,
            expires_at=now + timedelta(days=TOKEN_DAYS),
        )
    )
    await db.flush()
    return token


async def revoke_token(db: AsyncSession, prefix: str) -> bool:
    """Revoke the one active token with this prefix; False if there isn't exactly one."""
    active = (
        (
            await db.execute(
                select(PersonalAccessToken).where(
                    PersonalAccessToken.prefix == prefix.strip(),
                    PersonalAccessToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(active) != 1:
        return False
    active[0].revoked_at = datetime.now(UTC)
    await db.flush()
    return True


async def owner_of(db: AsyncSession, token: str | None) -> User | None:
    """The user a valid token acts for (recording that it was used), or None if the token is
    missing, unknown, revoked or expired."""
    if not token:
        return None
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(PersonalAccessToken, User)
            .join(User, User.id == PersonalAccessToken.user_id)
            .where(
                PersonalAccessToken.token_hash == _hash(token.strip()),
                PersonalAccessToken.revoked_at.is_(None),
                PersonalAccessToken.expires_at > now,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    stored, user = row
    if not user.can_use_app:  # an admin's or a disabled account's token (feature 011, FR-002)
        return None
    stored.last_used_at = now
    await db.flush()
    return user
