"""The four actions as buttons on the account pages (feature 011, task T024; FR-014;
contracts/admin-pages.md, "Actions")."""

import re
from pathlib import Path

import pytest
from admin_helpers import admin_client, make_admin, row_action, sign_in
from conftest import make_user
from document_helpers import add_confirmed_document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import AdminAuditEntry
from app.auth.models import User
from app.documents.models import DocType
from app.documents.storage import Storage, StorageUnavailable

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
ACTIONS = ("disable", "enable", "delete_account", "sign_out_everywhere", "reset_reading_limit")


def offered(html: str) -> set[str]:
    """The account actions (and the library's own delete and edit) a page offers."""
    return set(re.findall(r'data-sa-name="([^"]+)"', html)) & {*ACTIONS, "delete", "edit"}


async def exists(db: AsyncSession, user_id: object) -> bool:
    """Whether the account is in the database (asked afresh, not from this session's memory)."""
    return (await db.execute(select(User.id).where(User.id == user_id))).first() is not None


async def recorded(db: AsyncSession) -> list[str]:
    """The actions recorded so far."""
    return list((await db.execute(select(AdminAuditEntry.action))).scalars())


async def test_each_action_runs_from_its_button(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if a button doesn't run its action, or isn't recorded (FR-014, FR-016)."""
    await make_admin(db)
    alice = await make_user(db, "alice@example.com")

    async with admin_client(db, Storage(tmp_path)) as http:
        await sign_in(http)
        for name in ("disable", "enable", "sign_out_everywhere", "reset_reading_limit"):
            response = await row_action(http, name, alice.id)
            assert response.status_code == 200 and "redirect" in response.json(), name
        deleted = await row_action(http, "delete_account", alice.id)

    assert deleted.status_code == 200
    assert await exists(db, alice.id) is False
    assert await recorded(db) == [
        "disable",
        "enable",
        "sign_out_everywhere",
        "reset_reading_limit",
        "delete_account",
    ]


async def test_disable_and_re_enable_are_offered_by_state(db: AsyncSession) -> None:
    """Fails if Disable is offered for a disabled account or Re-enable for an active one, on the
    page or by a crafted request."""
    await make_admin(db)
    alice = await make_user(db, "alice@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        detail = f"/admin/account/detail?pk={alice.id}"
        active = offered((await http.get(detail)).text)
        wrong = await row_action(http, "enable", alice.id)
        await row_action(http, "disable", alice.id)
        disabled = offered((await http.get(detail)).text)

    assert "disable" in active and "enable" not in active
    assert wrong.status_code == 400
    assert "enable" in disabled and "disable" not in disabled


async def test_no_action_is_offered_or_accepted_for_an_admin_account(db: AsyncSession) -> None:
    """Fails if any action is shown for, or runs on, an admin account."""
    await make_admin(db)
    other = await make_admin(db, "other-admin@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        page = offered((await http.get(f"/admin/account/detail?pk={other.id}")).text)
        attempts = [await row_action(http, name, other.id) for name in ACTIONS]

    assert page == set()
    assert all(response.status_code == 400 for response in attempts)
    assert await recorded(db) == ["view_account"]


async def test_the_library_s_own_delete_and_edit_are_not_offered(db: AsyncSession) -> None:
    """Fails if the library's built-in delete or edit row actions are available (FR-012)."""
    await make_admin(db)
    alice = await make_user(db, "alice@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        listing = offered((await http.get("/admin/account/list")).text)
        response = await row_action(http, "delete", alice.id)

    assert not {"delete", "edit"} & listing
    assert response.status_code == 400
    assert await exists(db, alice.id) is True


async def test_a_storage_outage_says_nothing_was_deleted(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if a delete during a storage outage deletes the account or hides why."""

    class Down(Storage):
        """Storage that can't be reached."""

        async def delete(self, location: str) -> None:
            raise StorageUnavailable("Couldn't reach file storage. Try again later.")

    await make_admin(db)
    alice = await make_user(db, "alice@example.com")
    await add_confirmed_document(db, alice.id, DocType.SALARY_CERTIFICATE, SALARY)

    async with admin_client(db, Down(tmp_path)) as http:
        await sign_in(http)
        response = await row_action(http, "delete_account", alice.id)

    assert response.status_code == 400
    assert (
        response.json()["msg"] == "Storage can't be reached; nothing was deleted. Try again later."
    )
    assert await exists(db, alice.id) is True


async def test_an_action_without_the_csrf_token_is_refused(db: AsyncSession) -> None:
    """Fails if another site could make a signed-in admin's browser run an action."""
    await make_admin(db)
    alice = await make_user(db, "alice@example.com")

    async with admin_client(db) as http:
        await sign_in(http)
        response = await http.post(
            "/admin/_api/account/row-action", params={"pk": str(alice.id), "name": "disable"}
        )

    assert response.status_code == 403
    await db.refresh(alice)
    assert alice.disabled_at is None
