"""Login sessions (feature 002, task T013, research R2, R6).

The cookie holds a random token; only its SHA-256 hash is stored, so a leaked database can't be
used to log in. Sessions end at logout or 7 days after login, whichever comes first.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User

SESSION_LIFETIME = timedelta(days=7)  # FR-009


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(db: AsyncSession, user: User) -> str:
    """Start a session for the user and return the token for the cookie."""
    token = secrets.token_urlsafe(32)
    db.add(
        Session(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(UTC) + SESSION_LIFETIME,
        )
    )
    await db.flush()
    return token


async def get_user_for_token(db: AsyncSession, token: str) -> User | None:
    """The user a token belongs to, or None if unknown, logged out or expired.

    An expired session is deleted when it is next used (no background cleanup, research R6).
    """
    # One query for both: every protected request runs this (review of PR #27, item 8).
    row = (
        await db.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.token_hash == _hash_token(token))
        )
    ).one_or_none()
    if row is None:
        return None
    session, user = row
    if session.expires_at <= datetime.now(UTC):
        await db.delete(session)
        await db.flush()
        return None
    return user


async def delete_session(db: AsyncSession, token: str) -> None:
    """End the session for this token, if there is one (logout)."""
    await db.execute(delete(Session).where(Session.token_hash == _hash_token(token)))
    await db.flush()
