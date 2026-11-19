"""The dashboard counts and one account's overview (feature 011, task T014; FR-006, FR-008, FR-009;
research R6)."""

from datetime import UTC, datetime, timedelta

import pytest
from admin_helpers import make_admin
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.overview import Limit, account_overview, dashboard_counts
from app.auth.models import User
from app.documents.models import DocStatus, DocType, Document, ExtractionAttempt
from app.profile.service import save_profile
from app.rag.models import AskRequest
from app.workflow.models import Step, WorkflowRun

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def add_document(db: AsyncSession, user: User, status: DocStatus) -> None:
    """An unconfirmed document in this status (enough for counting)."""
    db.add(
        Document(
            user_id=user.id,
            doc_type=DocType.SALARY_CERTIFICATE,
            tax_year=PROFILE_YEAR,
            file_path="/data/uploads/synthetic.pdf",
            media_type="application/pdf",
            page_count=1,
            status=status,
        )
    )
    await db.flush()


def run(user: User, step: Step, fingerprint: str = "f" * 64) -> WorkflowRun:
    """A stored guided run at this step."""
    now = datetime(2026, 11, 1, tzinfo=UTC)
    return WorkflowRun(
        user_id=user.id,
        tax_year=PROFILE_YEAR,
        step=step,
        outputs_fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )


async def test_the_dashboard_counts_what_is_there(db: AsyncSession) -> None:
    """Fails if any of FR-006's counts is wrong, or admins are counted as taxpayers."""
    await make_admin(db)
    alice = await make_user(db, "alice@example.com")
    bob = await make_user(db, "bob@example.com")
    await save_profile(db, alice, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, alice.id, DocType.SALARY_CERTIFICATE, SALARY)
    await add_document(db, bob, DocStatus.FAILED)
    await add_document(db, bob, DocStatus.UPLOADED)
    db.add_all([run(alice, Step.GATE), run(bob, Step.DOCUMENT)])
    now = datetime.now(UTC)
    db.add_all(
        [ExtractionAttempt(user_id=alice.id, attempted_at=now) for _ in range(3)]
        + [ExtractionAttempt(user_id=bob.id, attempted_at=now)]
        + [ExtractionAttempt(user_id=bob.id, attempted_at=now - timedelta(hours=25))]
    )
    db.add_all(
        [AskRequest(user_id=alice.id, created_at=now - timedelta(minutes=5)) for _ in range(4)]
        + [AskRequest(user_id=bob.id, created_at=now - timedelta(hours=2))]
    )
    await db.flush()

    counts = await dashboard_counts(db)

    assert (counts.taxpayers, counts.profiles) == (2, 1)
    assert counts.documents == {"uploaded": 1, "confirmed": 1, "failed": 1}
    assert counts.runs_per_step == {"gate": 1, "document": 1}
    assert counts.readings_app == Limit(used=4, limit=100)
    assert counts.readings_busiest_user == Limit(used=3, limit=10)
    assert counts.questions_app == Limit(used=5, limit=200)
    assert counts.questions_busiest_user_hour == Limit(used=4, limit=30)


async def test_the_overview_shows_the_same_tax_result_as_the_tax_page(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the admin sees a different tax result from the one the user sees (FR-008)."""
    await save_profile(db, logged_in_user, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, logged_in_user.id, DocType.SALARY_CERTIFICATE, SALARY)
    tax_page = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    overview = await account_overview(db, logged_in_user)

    assert (overview.tax_year, overview.on_atl) == (PROFILE_YEAR, True)
    assert [(d.doc_type, d.status) for d in overview.documents] == [
        ("salary_certificate", "confirmed")
    ]
    assert overview.tax.model_dump() == tax_page
    assert overview.guided_step is None


async def test_without_a_profile_the_overview_shows_the_refusal(db: AsyncSession) -> None:
    """Fails if an account with no profile breaks the page or shows figures (spec edge case)."""
    user = await make_user(db, "new@example.com")

    overview = await account_overview(db, user)

    assert overview.tax_year is None and overview.on_atl is None
    assert overview.tax.blocked_reason == "needs_atl_answer"
    assert overview.tax.salary_tax is None


async def test_viewing_never_re_runs_or_changes_a_guided_run(db: AsyncSession) -> None:
    """Fails if opening an account re-runs its guided run (whose inputs changed since it ran) or
    changes anything about it (FR-009)."""
    user = await make_user(db, "taxpayer@example.com")
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    stored = run(user, Step.GATE, fingerprint="stale" + "0" * 59)
    db.add(stored)
    await db.flush()

    overview = await account_overview(db, user)

    await db.refresh(stored)
    assert overview.guided_step == "gate"
    assert (stored.step, stored.outputs_fingerprint, stored.updated_at) == (
        Step.GATE,
        "stale" + "0" * 59,
        datetime(2026, 11, 1, tzinfo=UTC),
    )
    assert (await db.execute(select(WorkflowRun))).scalars().all() == [stored]
