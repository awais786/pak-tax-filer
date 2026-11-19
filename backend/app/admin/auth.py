"""Signing in to the admin area (feature 011, task T013; FR-003 to FR-005; research R2).

Admins sign in with the app's own hashed-token sessions (feature 002), under their own cookie:
`admin_session`, HttpOnly, SameSite=Strict, path /admin, 8 hours. Only active admin accounts get
in; everyone else gets one generic answer. Failures are throttled like the app's login, under a
key the public login can't produce (THROTTLE_PREFIX), so failing there can't lock an admin out.
"""

from datetime import timedelta

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed
from starlette_admin.helpers import index_url

from app.auth import passwords, throttle
from app.auth.models import User
from app.auth.passwords import DUMMY_HASH
from app.auth.sessions import create_session, delete_session, get_user_for_token
from app.auth.users import get_user_by_email, normalize_email
from app.settings import get_settings

COOKIE = "admin_session"
LIFETIME = timedelta(hours=8)
# The app's own words (feature 002), so the two sign-ins can't be told apart.
INVALID = "Invalid email or password."
TOO_MANY_ATTEMPTS = "Too many attempts. Try again later."
# The public login's limits (app/auth/router.py), checked before anything is hashed or stored.
MAX_EMAIL, MAX_PASSWORD = 254, 1024
# Admin failures are throttled under this prefix. It starts with a space, which the public login
# can never produce (normalize_email strips spaces), so failing there can't lock an admin out.
THROTTLE_PREFIX = " admin:"


def is_admin(user: User | None) -> bool:
    """An active admin account."""
    return user is not None and user.is_admin and user.disabled_at is None


class AdminAuthProvider(AuthProvider):
    """The library's login page, backed by the app's users, throttle and sessions."""

    async def login(
        self, username: str, password: str, remember_me: bool, request: Request
    ) -> Response | None:
        """Admit an active admin and set the admin cookie; one answer for everything else."""
        del remember_me  # admin sessions are always 8 hours
        if len(username) > MAX_EMAIL or len(password) > MAX_PASSWORD:
            raise LoginFailed(INVALID)  # nothing stored for oversized input (review M2)
        db = request.state.session
        email = normalize_email(username)
        key = f"{THROTTLE_PREFIX}{email}"
        await throttle.one_attempt_at_a_time(db, key)
        if await throttle.is_throttled(db, key):
            raise LoginFailed(TOO_MANY_ATTEMPTS)
        user = await get_user_by_email(db, email)
        # Unknown emails still pay for a password check, so timing reveals nothing (002 R5).
        password_ok = await passwords.check_password(
            password, user.password_hash if user else DUMMY_HASH
        )
        if not password_ok or not is_admin(user):
            await throttle.record_failure(db, key)
            await db.commit()  # the library rolls back the failed request; keep the count
            raise LoginFailed(INVALID)
        assert user is not None  # is_admin checked it
        token = await create_session(db, user, lifetime=LIFETIME)
        response = RedirectResponse(index_url(request), status_code=303)
        response.set_cookie(
            COOKIE,
            token,
            max_age=int(LIFETIME.total_seconds()),
            path="/admin",
            httponly=True,
            secure=get_settings().cookie_secure,
            samesite="strict",
        )
        return response

    async def authenticate(self, request: Request) -> AdminUser | None:
        """The signed-in admin, from the admin cookie only; None sends them to the login page."""
        token = request.cookies.get(COOKIE)
        if not token:
            return None
        user = await get_user_for_token(request.state.session, token)
        if not is_admin(user):
            return None
        assert user is not None
        request.state.admin_id = user.id  # for the audit log
        return AdminUser(username=user.email)

    async def logout(self, request: Request) -> Response | None:
        """End the session and clear the cookie."""
        token = request.cookies.get(COOKIE)
        if token:
            await delete_session(request.state.session, token)
        response = RedirectResponse(
            str(request.url_for(request.app.state.ROUTE_NAME + ":login")), status_code=303
        )
        response.delete_cookie(COOKIE, path="/admin")
        return response
