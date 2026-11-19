"""The four actions on a taxpayer account (feature 011, task T022; FR-014, FR-015, FR-016;
research R7)."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from admin_helpers import make_admin
from conftest import make_user
from document_helpers import FakeBucketClient, add_confirmed_document
from google.api_core.exceptions import Forbidden
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import actions
from app.admin.models import AdminAuditEntry
from app.auth.models import Session, User
from app.auth.sessions import create_session, get_user_for_token
from app.documents.models import DocType, Document, ExtractionAttempt
from app.documents.service import DailyLimitReached, use_extraction
from app.documents.storage import Storage, StorageUnavailable
from app.tokens.models import PersonalAccessToken
from app.tokens.service import create_token, owner_of

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def audit_actions(db: AsyncSession) -> list[tuple[str, uuid.UUID]]:
    """Every recorded (action, account)."""
    rows = await db.execute(select(AdminAuditEntry.action, AdminAuditEntry.target_user_id))
    return [(row.action, row.target_user_id) for row in rows]


async def count(db: AsyncSession, model: type) -> int:
    """Rows of a table."""
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def with_files(db: AsyncSession, user: User, folder: Path, n: int = 2) -> list[Path]:
    """`n` confirmed documents whose files exist in `folder`."""
    files = []
    for i in range(n):
        document = await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
        path = folder / f"{user.id}-{i}.pdf"
        path.write_bytes(b"%PDF-1.4 synthetic")
        document.file_path = str(path)
        files.append(path)
    await db.flush()
    return files


class FailingStorage(Storage):
    """Storage that can't be reached from its `fail_on`-th delete onwards."""

    def __init__(self, folder: Path, fail_on: int) -> None:
        super().__init__(folder)
        self.calls = 0
        self.fail_on = fail_on

    async def delete(self, location: str) -> None:
        self.calls += 1
        if self.calls >= self.fail_on:
            raise StorageUnavailable("Couldn't reach file storage. Try again later.")
        await super().delete(location)


async def test_disable_signs_out_removes_tokens_and_is_refused_everywhere(
    db: AsyncSession,
) -> None:
    """Fails if a disabled account keeps a session or token, or isn't marked (FR-014a)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    session = await create_session(db, user)
    token = await create_token(db, user.id, "laptop")

    await actions.disable_account(db, admin.id, user.id)

    await db.refresh(user)
    assert user.disabled_at is not None and not user.can_use_app
    assert await get_user_for_token(db, session) is None
    assert await owner_of(db, token) is None
    assert await count(db, PersonalAccessToken) == 0
    assert await audit_actions(db) == [("disable", user.id)]


async def test_re_enable_lets_the_account_in_again_without_old_tokens(db: AsyncSession) -> None:
    """Fails if re-enabling doesn't clear the mark, or brings tokens back (FR-014b)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    await create_token(db, user.id, "laptop")
    await actions.disable_account(db, admin.id, user.id)

    await actions.enable_account(db, admin.id, user.id)

    await db.refresh(user)
    assert user.disabled_at is None and user.can_use_app
    assert await count(db, PersonalAccessToken) == 0
    assert await audit_actions(db) == [("disable", user.id), ("enable", user.id)]


async def test_delete_removes_the_files_then_the_account(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if a stored file or any record of the account is left (FR-014c, SC-005)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    files = await with_files(db, user, tmp_path)
    await create_session(db, user)

    await actions.delete_account(db, Storage(tmp_path), admin.id, user.id)

    assert not any(path.exists() for path in files)
    assert (await db.get(User, user.id)) is None
    assert (await count(db, Document), await count(db, Session)) == (0, 0)
    assert await audit_actions(db) == [("delete_account", user.id)]


async def test_a_storage_outage_deletes_no_record_and_a_retry_finishes(
    db: AsyncSession, tmp_path: Path
) -> None:
    """Fails if an outage halfway deletes any record, or a retry can't finish (FR-014c)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    files = await with_files(db, user, tmp_path)

    with pytest.raises(actions.StorageDown, match="nothing was deleted"):
        await actions.delete_account(db, FailingStorage(tmp_path, fail_on=2), admin.id, user.id)

    assert (await db.get(User, user.id)) is not None and await count(db, Document) == 2
    assert await audit_actions(db) == []
    await actions.delete_account(db, Storage(tmp_path), admin.id, user.id)
    assert not any(path.exists() for path in files)
    assert (await db.get(User, user.id)) is None


async def test_deleting_an_account_already_gone_says_so(db: AsyncSession) -> None:
    """Fails if a second admin's delete of a deleted account errors oddly or is recorded."""
    admin = await make_admin(db)

    with pytest.raises(actions.AccountGone):
        await actions.delete_account(db, Storage(Path("/nowhere")), admin.id, uuid.uuid4())

    assert await audit_actions(db) == []


async def test_sign_out_everywhere_keeps_access_tokens(db: AsyncSession) -> None:
    """Fails if a session survives, or the user's tokens are removed (FR-014d)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    phone, laptop = await create_session(db, user), await create_session(db, user)
    token = await create_token(db, user.id, "laptop")

    await actions.sign_out_everywhere(db, admin.id, user.id)

    assert await get_user_for_token(db, phone) is None
    assert await get_user_for_token(db, laptop) is None
    assert (await owner_of(db, token)) is not None
    assert await audit_actions(db) == [("sign_out_everywhere", user.id)]


async def test_resetting_the_reading_limit_allows_readings_again(db: AsyncSession) -> None:
    """Fails if a user at the daily limit still can't have a document read (FR-014e)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    now = datetime.now(UTC)
    db.add_all([ExtractionAttempt(user_id=user.id, attempted_at=now) for _ in range(10)])
    db.add(ExtractionAttempt(user_id=user.id, attempted_at=now - timedelta(hours=30)))
    await db.flush()
    with pytest.raises(DailyLimitReached):
        await use_extraction(db, user.id)

    await actions.reset_reading_limit(db, admin.id, user.id)

    await use_extraction(db, user.id)  # counts one new attempt
    assert await count(db, ExtractionAttempt) == 2  # the old one stays; the new one is counted
    assert await audit_actions(db) == [("reset_reading_limit", user.id)]


@pytest.mark.parametrize(
    "action",
    ["disable_account", "enable_account", "sign_out_everywhere", "reset_reading_limit"],
)
async def test_no_action_applies_to_an_admin_account(db: AsyncSession, action: str) -> None:
    """Fails if an admin can act on another admin (no lock-outs; admins are managed from the
    command line)."""
    admin = await make_admin(db)
    other = await make_admin(db, "other-admin@example.com")

    with pytest.raises(actions.TargetIsAdmin):
        await getattr(actions, action)(db, admin.id, other.id)

    assert await audit_actions(db) == []


async def test_deleting_an_admin_account_is_refused(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if an admin account can be deleted from the admin area."""
    admin = await make_admin(db)
    other = await make_admin(db, "other-admin@example.com")

    with pytest.raises(actions.TargetIsAdmin):
        await actions.delete_account(db, Storage(tmp_path), admin.id, other.id)

    assert (await db.get(User, other.id)) is not None


async def test_delete_locks_the_account_before_reading_its_files(
    db: AsyncSession, tmp_path: Path
) -> None:
    """Fails if an upload still in flight could add a file after the delete read the list (review
    M1): the account row is locked first, so an in-flight upload commits before the files are read
    and a later one fails on its foreign key (and removes its own file)."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    statements: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        statements.append(" ".join(statement.split()).upper())

    engine = (await db.connection()).sync_connection.engine  # type: ignore[union-attr]
    event.listen(engine, "before_cursor_execute", record)
    try:
        await actions.delete_account(db, Storage(tmp_path), admin.id, user.id)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    lock = next(i for i, s in enumerate(statements) if "FROM USERS" in s and "FOR UPDATE" in s)
    files = next(i for i, s in enumerate(statements) if "DOCUMENTS.FILE_PATH" in s)
    assert lock < files


async def test_delete_removes_the_files_from_the_bucket_too(
    db: AsyncSession, tmp_path: Path
) -> None:
    """Fails if deleting an account leaves its uploads in the private Cloud Storage bucket (the
    deployed app's storage, feature 003 FR-018), or deletes the account when Google is down."""
    admin = await make_admin(db)
    user = await make_user(db, "alice@example.com")
    client = FakeBucketClient()
    storage = Storage(tmp_path, bucket="uploads", client=client)
    for _ in range(2):
        document = await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
        document.file_path = await storage.save(user.id, b"%PDF-1.4", "pdf", "application/pdf")
    await db.flush()
    assert len(client.buckets["uploads"]) == 2

    client.fail = Forbidden("no access")  # type: ignore[no-untyped-call]  # google-api-core is untyped
    with pytest.raises(actions.StorageDown):
        await actions.delete_account(db, storage, admin.id, user.id)
    assert len(client.buckets["uploads"]) == 2 and await count(db, Document) == 2

    client.fail = None
    await actions.delete_account(db, storage, admin.id, user.id)

    assert not client.buckets["uploads"]
    assert (await count(db, Document), await count(db, User)) == (0, 1)  # the admin remains
