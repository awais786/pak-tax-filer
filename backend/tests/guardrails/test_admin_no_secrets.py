"""Guardrail: no admin page shows a password, session or access token, in any form (feature 011,
task T017; FR-013, SC-003)."""

import hashlib

import pytest
from admin_helpers import admin_client, make_admin, sign_in
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import audit
from app.auth.models import Session, User
from app.auth.sessions import create_session
from app.documents.models import DocType
from app.profile.service import save_profile
from app.tokens.models import PersonalAccessToken
from app.tokens.service import create_token

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def test_no_admin_page_shows_a_secret(db: AsyncSession) -> None:
    """Fails if any admin page carries a password hash, a session token or its hash, or an access
    token or its hash."""
    admin = await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")
    await save_profile(db, taxpayer, PROFILE_YEAR, on_atl=True)
    document = await add_confirmed_document(db, taxpayer.id, DocType.SALARY_CERTIFICATE, SALARY)
    session_token = await create_session(db, taxpayer)
    access_token = await create_token(db, taxpayer.id, "laptop")
    await audit.record(db, admin.id, "view_account", taxpayer.id)
    secrets = {session_token, access_token, hashlib.sha256(session_token.encode()).hexdigest()}
    secrets |= set((await db.execute(select(User.password_hash))).scalars())
    secrets |= set((await db.execute(select(Session.token_hash))).scalars())
    secrets |= set((await db.execute(select(PersonalAccessToken.token_hash))).scalars())

    pages = [
        "/admin/",
        "/admin/telemetry",
        f"/admin/account/detail?pk={taxpayer.id}",
        f"/admin/account/detail?pk={admin.id}",
        *(f"/admin/{key}/list" for key in ("account", "document", "corpus-document", "audit-log")),
    ]
    async with admin_client(db) as http:
        await sign_in(http)
        responses = {path: await http.get(path) for path in pages}

    del document
    for path, response in responses.items():
        assert response.status_code == 200, path
        for secret in secrets:
            assert secret not in response.text, path
