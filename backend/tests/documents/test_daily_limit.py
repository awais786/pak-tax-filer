"""Daily extraction limits (feature 003, FR-017; 002 task T048 and its review).

Each upload or retry calls the free AI quota. With open sign-up (002, User Story 6), one user
gets at most 10 in any 24 hours, and the whole app at most 100, since anyone can make more
accounts. Over a limit, nothing is stored and the AI isn't called.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from document_helpers import make_pdf, upload
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password
from app.documents.extraction.client import ExtractionResult, FakeExtractor, failed
from app.documents.models import Document, ExtractionAttempt

pytestmark = pytest.mark.anyio

USER_LIMIT = "Daily limit reached: 10 extractions per 24 hours. Try again later."
APP_LIMIT = "The app's daily extraction limit has been reached. Try again later."


async def add_attempts(
    db: AsyncSession, user_id: uuid.UUID, count: int, hours_ago: float = 1
) -> None:
    """`count` earlier extraction attempts for the user, `hours_ago` hours ago."""
    at = datetime.now(UTC) - timedelta(hours=hours_ago)
    db.add_all(ExtractionAttempt(user_id=user_id, attempted_at=at) for _ in range(count))
    # Committed (to a savepoint the test still rolls back), so a refused request keeps them.
    await db.commit()


async def attempts(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many attempts are recorded for the user."""
    return (
        await db.execute(
            select(func.count())
            .select_from(ExtractionAttempt)
            .where(ExtractionAttempt.user_id == user_id)
        )
    ).scalar_one()


async def other_user(db: AsyncSession) -> uuid.UUID:
    """Another account's id."""
    other = User(email="other@example.com", password_hash=hash_password("other-pass"))
    db.add(other)
    await db.commit()
    return other.id


def files_in(folder: Path) -> list[Path]:
    """Every stored file under the uploads folder."""
    return [path for path in folder.rglob("*") if path.is_file()]


async def retry(client: AsyncClient, document_id: str) -> int:
    """POST a retry; its status code."""
    return (await client.post(f"/api/documents/{document_id}/retry", json={})).status_code


async def test_the_eleventh_upload_is_refused_before_anything_happens(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    fake_extractor: FakeExtractor,
    upload_dir: Path,
) -> None:
    """Fails if an upload over the limit stores a file, creates a document or calls the AI."""
    user_id = user_with_profile.id
    await add_attempts(db, user_id, 10)

    response = await upload(client, make_pdf())

    assert response.status_code == 429
    assert response.json() == {"detail": USER_LIMIT}
    assert not fake_extractor.calls
    assert (await db.scalars(select(Document))).first() is None
    assert not files_in(upload_dir)
    assert await attempts(db, user_id) == 10


@pytest.mark.usefixtures("fake_extractor")
async def test_the_file_checks_come_before_the_limit(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a file that would be refused anyway is answered 429, or counted (contract)."""
    user_id = user_with_profile.id
    await add_attempts(db, user_id, 10)

    response = await upload(client, b"PK\x03\x04 not a pdf", "certificate.docx")

    assert response.status_code == 415
    assert await attempts(db, user_id) == 10


@pytest.mark.usefixtures("fake_extractor")
async def test_an_upload_under_the_limit_works_and_is_counted(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the 10th extraction is refused, or an upload isn't counted."""
    user_id = user_with_profile.id
    await add_attempts(db, user_id, 9)

    response = await upload(client, make_pdf())

    assert response.status_code == 201
    assert await attempts(db, user_id) == 10


async def test_retries_count_and_are_refused_over_the_limit(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if retrying could bypass the limit (each retry calls the AI too)."""
    user_id = user_with_profile.id
    fake_extractor.result = failed("The AI service is busy. Try again in a minute.")
    document_id = (await upload(client, make_pdf())).json()["id"]
    assert await attempts(db, user_id) == 1

    assert await retry(client, document_id) == 200
    assert await attempts(db, user_id) == 2

    await add_attempts(db, user_id, 8)
    calls = len(fake_extractor.calls)
    refused = await client.post(f"/api/documents/{document_id}/retry", json={})

    assert refused.status_code == 429
    assert refused.json() == {"detail": USER_LIMIT}
    assert len(fake_extractor.calls) == calls


@pytest.mark.usefixtures("fake_extractor")
async def test_retrying_a_document_that_did_not_fail_is_409_and_not_counted(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a retry that can't run is counted, or the limit hides the contract's 409."""
    user_id = user_with_profile.id
    document_id = (await upload(client, make_pdf())).json()["id"]  # needs_review

    assert await retry(client, document_id) == 409
    assert await attempts(db, user_id) == 1

    await add_attempts(db, user_id, 9)
    assert await retry(client, document_id) == 409


async def test_a_retry_with_the_stored_file_missing_is_not_counted(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    fake_extractor: FakeExtractor,
    upload_dir: Path,
) -> None:
    """Fails if a retry that never calls the AI uses up the limit."""
    user_id = user_with_profile.id
    fake_extractor.result = failed("The AI service is busy. Try again in a minute.")
    document_id = (await upload(client, make_pdf())).json()["id"]
    for path in files_in(upload_dir):
        path.unlink()

    assert await retry(client, document_id) == 200
    assert await attempts(db, user_id) == 1


@pytest.mark.usefixtures("fake_extractor")
async def test_deleting_a_document_does_not_reset_the_count(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if upload-and-delete could be repeated forever."""
    user_id = user_with_profile.id
    document_id = (await upload(client, make_pdf())).json()["id"]

    deleted = await client.request("DELETE", f"/api/documents/{document_id}", json={})

    assert deleted.status_code == 204
    assert await attempts(db, user_id) == 1


async def test_a_wrong_type_upload_still_counts(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if a refused wrong-type file (which did call the AI) isn't counted: the request
    rolls back, so the attempt must have been committed before extraction."""
    user_id = user_with_profile.id
    fake_extractor.result = ExtractionResult(
        failure_reason="This doesn't look like a salary certificate.", wrong_type=True
    )

    assert (await upload(client, make_pdf())).status_code == 422
    assert await attempts(db, user_id) == 1


@pytest.mark.usefixtures("fake_extractor")
async def test_attempts_older_than_24_hours_do_not_count(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if yesterday's uploads still block today's."""
    await add_attempts(db, user_with_profile.id, 10, hours_ago=25)

    assert (await upload(client, make_pdf())).status_code == 201


@pytest.mark.usefixtures("fake_extractor")
async def test_another_users_attempts_do_not_use_up_mine(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if one user's uploads use up someone else's limit."""
    user_id = user_with_profile.id
    await add_attempts(db, await other_user(db), 10)

    assert (await upload(client, make_pdf())).status_code == 201
    assert await attempts(db, user_id) == 1


@pytest.mark.usefixtures("user_with_profile")
async def test_the_whole_app_stops_at_100_a_day(
    client: AsyncClient,
    db: AsyncSession,
    fake_extractor: FakeExtractor,
    upload_dir: Path,
) -> None:
    """Fails if making more accounts could use up the shared free quota (002 review H2)."""
    await add_attempts(db, await other_user(db), 100)

    response = await upload(client, make_pdf())

    assert response.status_code == 429
    assert response.json() == {"detail": APP_LIMIT}
    assert not fake_extractor.calls
    assert not files_in(upload_dir)


GOOGLE_BUSY = failed("Google's AI service is busy.", service_failed=True)


async def test_an_upload_google_failed_to_answer_is_not_counted(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if a try lost to Google's side (a 5xx, e.g. its 60-second 504, or no connection)
    uses up one of the user's 10 (FR-017, amended 2026-11-13); the file stays, for Retry."""
    fake_extractor.result = GOOGLE_BUSY

    response = await upload(client, make_pdf())

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert await attempts(db, user_with_profile.id) == 0


async def test_a_retry_google_failed_to_answer_is_not_counted(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if retrying while Google is still busy keeps costing the user tries."""
    fake_extractor.result = GOOGLE_BUSY
    document_id = (await upload(client, make_pdf())).json()["id"]

    assert await retry(client, document_id) == 200
    assert await attempts(db, user_with_profile.id) == 0


async def test_a_failure_of_the_document_itself_still_counts(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if a failure Google answered (an unreadable file) stops counting: the AI was used."""
    fake_extractor.result = failed("The AI service couldn't read this file.")

    await upload(client, make_pdf())

    assert await attempts(db, user_with_profile.id) == 1
