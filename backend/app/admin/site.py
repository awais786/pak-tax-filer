"""The admin area's site: starlette-admin mounted at /admin (feature 011, task T013; research R1).

`build_admin(app, sessions)` mounts it on a FastAPI app; `sessions` is the session factory the
library opens one session per request from: `AppSessions()` in the app (built on first use, so
importing the app needs no DATABASE_URL), or one bound to a test's rolled-back connection.
"""

import logging
import os
from pathlib import Path
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from jinja2 import PackageLoader, PrefixLoader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette_admin.contrib.sqla import Admin

from app.admin.auth import AdminAuthProvider
from app.admin.views import dashboard_view, model_views, telemetry_view
from app.db import get_sessionmaker
from app.documents.router import get_storage
from app.documents.storage import Storage
from app.settings import admin_secret_key


class AppSessions(async_sessionmaker[AsyncSession]):
    """The app's session factory, looked up on each call rather than when the app is imported.
    An async_sessionmaker itself, because that is how the library recognises an async one."""

    def __init__(self) -> None:
        super().__init__(expire_on_commit=False)

    def __call__(self, **local_kw: Any) -> AsyncSession:
        return get_sessionmaker()(**local_kw)


def build_admin(
    app: FastAPI,
    sessions: async_sessionmaker[AsyncSession],
    storage: Callable[[], Storage] | None = None,
) -> Admin:
    """Mount the admin area on `app` at /admin and return it; `storage` gives the uploaded
    files' storage (the app's own by default; tests pass a temporary folder's)."""
    # The library logs typed login emails and record ids at INFO and WARNING; personal data
    # never reaches our logs (.claude/rules/security.md), so only its critical errors do.
    logging.getLogger("starlette_admin").setLevel(logging.CRITICAL)
    # Without ADMIN_SECRET_KEY the library makes a start-up key and warns once (research R3).
    secret_key = admin_secret_key(os.environ)
    admin = Admin(
        sessions,
        title="PakTaxFiler admin",
        base_url="/admin",
        auth_provider=AdminAuthProvider(),
        secret_key=secret_key,
        templates_dir=str(Path(__file__).parent / "templates"),
        # The library's own pages under a prefix, so our base.html can extend its base.html.
        additional_loaders=[
            PrefixLoader({"starlette_admin": PackageLoader("starlette_admin", "templates")})
        ],
        index_view=dashboard_view(),
    )
    for view in model_views(storage or get_storage):
        admin.add_view(view)
    admin.add_view(telemetry_view())
    admin.mount_to(app)
    return admin
