"""The admin pages (feature 011, task T016; FR-006 to FR-012, FR-016, FR-018;
contracts/admin-pages.md, "Pages")."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from admin_helpers import ADMIN_EMAIL, admin_client, make_admin, sign_in
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from rag_helpers import a_corpus
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import audit
from app.admin.models import AdminAuditEntry
from app.documents.models import DocType
from app.profile.service import save_profile
from app.rag.models import CorpusDocument, Passage

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
KEYS = ("account", "document", "corpus-document", "audit-log")


async def entries(db: AsyncSession) -> list[AdminAuditEntry]:
    """Every audit entry."""
    return list((await db.execute(select(AdminAuditEntry))).scalars())


async def test_the_dashboard_shows_the_counts(db: AsyncSession) -> None:
    """Fails if the dashboard doesn't show FR-006's counts."""
    await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")
    await add_confirmed_document(db, taxpayer.id, DocType.SALARY_CERTIFICATE, SALARY)

    async with admin_client(db) as http:
        await sign_in(http)
        page = (await http.get("/admin/")).text

    for title in (
        "Taxpayer accounts",
        "Profiles set up",
        "Documents confirmed",
        "Documents failed",
        "Document readings today",
        "Ask questions today",
    ):
        assert title in page, title
    assert "1 of 100" in page or "0 of 100" in page  # readings against the app-wide limit


async def test_the_accounts_list_shows_and_searches_accounts(db: AsyncSession) -> None:
    """Fails if the list lacks an account or search by email doesn't narrow it (FR-007)."""
    await make_admin(db)
    await make_user(db, "alice@example.com")
    await make_user(db, "bob@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        everyone = (await http.get("/admin/account/list")).text
        found = (await http.get("/admin/account/list", params={"q": "alice"})).text

    assert "alice@example.com" in everyone and "bob@example.com" in everyone
    assert "alice@example.com" in found and "bob@example.com" not in found


async def test_opening_an_account_shows_its_overview_and_is_recorded_once(
    db: AsyncSession,
) -> None:
    """Fails if the account page lacks the overview (FR-008), or opening it doesn't write exactly
    one view_account entry (FR-016), or list pages write any."""
    admin = await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")
    await save_profile(db, taxpayer, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, taxpayer.id, DocType.SALARY_CERTIFICATE, SALARY)

    async with admin_client(db) as http:
        await sign_in(http)
        await http.get("/admin/account/list")
        assert await entries(db) == []
        page = await http.get("/admin/account/detail", params={"pk": str(taxpayer.id)})

    assert page.status_code == 200
    for text in (PROFILE_YEAR, "On the ATL", "salary_certificate", "confirmed", "Rs 72,000"):
        assert text in page.text, text
    [entry] = await entries(db)
    assert (entry.admin_id, entry.action, entry.target_user_id) == (
        admin.id,
        "view_account",
        taxpayer.id,
    )


async def test_documents_are_listed_without_their_files(db: AsyncSession) -> None:
    """Fails if the documents list lacks a column, or offers a document's file or detail page
    (FR-010)."""
    await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")
    document = await add_confirmed_document(db, taxpayer.id, DocType.SALARY_CERTIFICATE, SALARY)

    async with admin_client(db) as http:
        await sign_in(http)
        listing = (await http.get("/admin/document/list")).text
        detail = await http.get("/admin/document/detail", params={"pk": str(document.id)})

    for text in ("salary_certificate", "confirmed", PROFILE_YEAR, "alice@example.com"):
        assert text in listing, text
    assert document.file_path not in listing and "/_files/" not in listing
    assert detail.status_code in (403, 404)


async def test_the_law_library_lists_documents_with_passage_counts(db: AsyncSession) -> None:
    """Fails if a corpus document or its passage count is missing (FR-011)."""
    await make_admin(db)
    await a_corpus(db)
    counts = dict(
        (
            await db.execute(
                select(Passage.document_id, func.count()).group_by(Passage.document_id)
            )
        ).all()
    )
    titles = dict((await db.execute(select(CorpusDocument.id, CorpusDocument.title))).all())

    async with admin_client(db) as http:
        await sign_in(http)
        page = (await http.get("/admin/corpus-document/list")).text

    for document_id, count in counts.items():
        assert titles[document_id] in page
        assert re.search(rf">\s*{count}\s*<", page), (document_id, count)


async def test_the_audit_log_names_accounts_newest_first(db: AsyncSession) -> None:
    """Fails if the log isn't newest first, or doesn't name existing accounts by email and
    deleted ones by id (FR-018)."""
    admin = await make_admin(db)
    alice = await make_user(db, "alice@example.com")
    gone = uuid.uuid4()
    await audit.record(db, admin.id, "view_account", alice.id)
    await audit.record(db, admin.id, "delete_account", gone)
    # now() is the transaction's start in PostgreSQL, so give the two entries distinct times
    # (each action is its own request in the app).
    await db.execute(
        update(AdminAuditEntry)
        .where(AdminAuditEntry.action == "view_account")
        .values(at=datetime.now(UTC) - timedelta(minutes=5))
    )

    async with admin_client(db) as http:
        await sign_in(http)
        page = (await http.get("/admin/audit-log/list")).text

    assert ADMIN_EMAIL in page and "alice@example.com" in page and str(gone) in page
    assert page.index("delete_account") < page.index("view_account")


@pytest.mark.parametrize("key", KEYS)
async def test_nothing_can_be_created_edited_deleted_exported_or_imported(
    db: AsyncSession, key: str
) -> None:
    """Fails if any admin view offers create, edit, delete, inline edit, export or import
    (FR-012)."""
    await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        listing = (await http.get(f"/admin/{key}/list")).text
        create = await http.get(f"/admin/{key}/create")
        edit = await http.get(f"/admin/{key}/edit", params={"pk": str(taxpayer.id)})
        inline = await http.get(f"/admin/_api/{key}/inline-edit")

    assert create.status_code in (403, 404)
    assert edit.status_code in (403, 404)
    assert inline.status_code in (403, 404, 405)
    assert f"/admin/{key}/create" not in listing and f"/admin/{key}/edit" not in listing
    for word in ('value="delete"', 'data-name="delete"', 'value="export', 'data-name="export'):
        assert word not in listing, word
    assert (await db.execute(select(func.count()).select_from(AdminAuditEntry))).scalar_one() == 0


async def test_admin_pages_load_nothing_from_outside_sites(db: AsyncSession) -> None:
    """Fails if an admin page makes the browser fetch from another site (research R12: the
    library's base page imported a font from rsms.me)."""
    await make_admin(db)
    taxpayer = await make_user(db, "alice@example.com")

    async with admin_client(db) as http:
        login = (await http.get("/admin/login")).text
        await sign_in(http)
        pages = [login] + [
            (await http.get(path)).text
            for path in (
                "/admin/",
                "/admin/account/list",
                f"/admin/account/detail?pk={taxpayer.id}",
            )
        ]

    for page in pages:
        loads = re.findall(
            r'(?:src|href)="(https?://[^"]+)"|@import url\(\'?(https?://[^\')]+)', page
        )
        outside = [
            url for pair in loads for url in pair if url and urlsplit(url).hostname != "test"
        ]
        assert outside == []


async def test_what_users_typed_is_shown_escaped(db: AsyncSession) -> None:
    """Fails if an email with HTML in it runs as script on an admin page (review: the admin pages
    share the taxpayer app's origin, so XSS there would act with admin rights)."""
    admin = await make_admin(db)
    evil = await make_user(db, "<script>alert(1)</script>@example.com")
    await audit.record(db, admin.id, "view_account", evil.id)

    async with admin_client(db) as http:
        await sign_in(http)
        pages = [
            (await http.get(path)).text
            for path in (
                "/admin/account/list",
                f"/admin/account/detail?pk={evil.id}",
                "/admin/audit-log/list",
            )
        ]

    for page in pages:
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page
