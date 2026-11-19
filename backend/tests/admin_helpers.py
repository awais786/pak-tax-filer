"""Helpers for the admin-area tests (feature 011).

`admin_client` serves the real app with the admin area mounted on the test's own connection, so
admin pages see what the test added and everything is rolled back afterwards, like `client`.
"""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.site import build_admin
from app.auth.models import User
from app.auth.passwords import hash_password
from app.documents.storage import Storage

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-s3cret-pass"
INVALID = "Invalid email or password."


async def make_admin(db: AsyncSession, email: str = ADMIN_EMAIL) -> User:
    """A synthetic admin account with ADMIN_PASSWORD."""
    admin = User(email=email, password_hash=hash_password(ADMIN_PASSWORD), is_admin=True)
    db.add(admin)
    await db.flush()
    return admin


@asynccontextmanager
async def admin_client(
    db: AsyncSession, storage: Storage | None = None
) -> AsyncIterator[AsyncClient]:
    """A client for a fresh app whose admin area uses the test's rolled-back connection (and
    `storage` for uploaded files, if given)."""
    connection = await db.connection()
    sessions = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    app = FastAPI()
    build_admin(app, sessions, storage=(lambda: storage) if storage else None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
        yield http


def csrf_token(html: str) -> str:
    """The CSRF token of the first form on a page."""
    match = re.search(r'name="csrftoken"[^>]*value="([^"]+)"', html) or re.search(
        r'value="([^"]+)"[^>]*name="csrftoken"', html
    )
    assert match, "no CSRF token on the page"
    return match.group(1)


async def sign_in(
    http: AsyncClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD
) -> Response:
    """Post the admin login form (with its CSRF token); returns the response."""
    page = await http.get("/admin/login")
    return await http.post(
        "/admin/login",
        data={"username": email, "password": password, "csrftoken": csrf_token(page.text)},
    )


async def row_action(
    http: AsyncClient, name: str, pk: object, page: str = "/admin/account/list"
) -> Response:
    """Post an account row action (with the CSRF token from `page`), as the page's button does."""
    token = csrf_token((await http.get(page)).text)
    return await http.post(
        "/admin/_api/account/row-action",
        params={"pk": str(pk), "name": name},
        data={"csrftoken": token},
    )
