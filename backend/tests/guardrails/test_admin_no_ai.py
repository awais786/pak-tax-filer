"""Guardrail: nothing in the admin area calls an AI model (feature 011, task T030; FR-024;
constitution Principle I; research R14).

Google's client is made to fail on creation, so any path from an admin page or action to Gemini
fails the test. (The admin area takes no FastAPI dependencies, so faking the app's AI
dependencies alone would prove nothing here.) The import ban in .importlinter backs this up.
"""

from pathlib import Path

import pytest
from admin_helpers import admin_client, make_admin, row_action, sign_in
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from google import genai
from rag_helpers import a_corpus
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocType
from app.documents.storage import Storage
from app.profile.service import save_profile

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def test_every_admin_page_and_action_works_with_no_ai_at_all(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fails if an admin page or action reaches Gemini."""

    def no_ai(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the admin area called Gemini")

    monkeypatch.setattr(genai, "Client", no_ai)
    await make_admin(db)
    await a_corpus(db)
    alice = await make_user(db, "alice@example.com")
    await save_profile(db, alice, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, alice.id, DocType.SALARY_CERTIFICATE, SALARY)

    async with admin_client(db, Storage(tmp_path)) as http:
        await sign_in(http)
        pages = [
            "/admin/",
            "/admin/telemetry",
            f"/admin/account/detail?pk={alice.id}",
            *(
                f"/admin/{key}/list"
                for key in ("account", "document", "corpus-document", "audit-log")
            ),
        ]
        for path in pages:
            assert (await http.get(path)).status_code == 200, path
        for name in ("disable", "enable", "sign_out_everywhere", "reset_reading_limit"):
            assert (await row_action(http, name, alice.id)).status_code == 200, name
        assert (await row_action(http, "delete_account", alice.id)).status_code == 200
