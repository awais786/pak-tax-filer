"""POST /api/auth/login, /signup, /logout and GET /api/auth/me (feature 002, tasks T015, T021,
T047).

Contract: specs/002-auth-foundation/contracts/auth-api.md. Research: R2 (cookie), R3 (JSON only),
R4 (throttling), R5 (same answer and same work for unknown emails).
"""

from typing import Annotated, Literal, TypedDict

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import sessions, throttle
from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.auth import passwords
from app.auth.passwords import DUMMY_HASH
from app.auth.users import (
    EmailTaken,
    PasswordTooShort,
    create_user,
    get_user_by_email,
    normalize_email,
)
from app.db import get_db
from app.settings import get_settings

COOKIE_NAME = "session"
INVALID_LOGIN = "Invalid email or password."
TOO_MANY_ATTEMPTS = "Too many attempts. Try again later."
EMAIL_TAKEN = "An account with this email already exists. Log in instead."


router = APIRouter(prefix="/api/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class LoginRequest(BaseModel):
    """Login body."""

    # Bounded so oversized values are refused before any hashing or storing (review L1).
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class SignupRequest(BaseModel):
    """Sign-up body (contract): an email-shaped name and a password, bounded like login's."""

    email: str = Field(min_length=3, max_length=254, pattern="@")
    password: str = Field(min_length=1, max_length=1024)


class EmailResponse(BaseModel):
    """The logged-in user's email, and nothing else."""

    email: str


class _CookieSettings(TypedDict):
    path: str
    httponly: bool
    samesite: Literal["lax"]
    secure: bool


def _cookie_settings() -> _CookieSettings:
    """The session cookie's settings, shared by login and logout: a browser only clears a cookie
    whose path and flags match the one it holds (review of PR #27, item 10)."""
    return {
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": get_settings().cookie_secure,
    }


@router.post("/login", dependencies=[Depends(require_json)])
async def login(body: LoginRequest, response: Response, db: DbSession) -> EmailResponse:
    """Log in with email and password; on success set the session cookie."""
    email = normalize_email(body.email)

    await throttle.one_attempt_at_a_time(db, email)

    # Throttled attempts don't check the password at all (contract).
    if await throttle.is_throttled(db, email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)

    user = await get_user_by_email(db, email)
    # Unknown emails still pay for an Argon2 check, so timing doesn't reveal them (R5).
    password_ok = await passwords.check_password(
        body.password, user.password_hash if user else DUMMY_HASH
    )
    # Admins and disabled accounts get a wrong password's answer (feature 011, FR-002).
    if user is None or not password_ok or not user.can_use_app:
        await throttle.record_failure(db, email)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    await _start_session(db, user, response)
    return EmailResponse(email=user.email)


@router.post("/signup", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_json)])
async def signup(body: SignupRequest, response: Response, db: DbSession) -> EmailResponse:
    """Create an account and log it in, exactly as login does (FR-024 to FR-026, research R15)."""
    try:
        user = await create_user(db, body.email, body.password)
    except PasswordTooShort as short:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(short)) from short
    except EmailTaken as taken:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from taken
    await _start_session(db, user, response)
    return EmailResponse(email=user.email)


async def _start_session(db: AsyncSession, user: User, response: Response) -> None:
    """Create a session, commit, and set its cookie: the one way login and sign-up log in."""
    token = await sessions.create_session(db, user)
    await db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(sessions.SESSION_LIFETIME.total_seconds()),
        **_cookie_settings(),
    )


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_json)]
)
async def logout(
    response: Response,
    db: DbSession,
    session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> None:
    """End the current session, if any, and clear the cookie. Always 204."""
    if session:
        await sessions.delete_session(db, session)
        await db.commit()
    response.delete_cookie(COOKIE_NAME, **_cookie_settings())


@router.get("/me")
async def me(user: Annotated[User, Depends(current_user)]) -> EmailResponse:
    """The logged-in user's email and nothing else (FR-011); 401 when not logged in."""
    return EmailResponse(email=user.email)
