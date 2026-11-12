"""GET and PUT /api/wealth/{tax_year} (feature 005, tasks T010, T020; contracts/wealth-api.md).

Entries are stored; the reconciliation is recalculated on every request from the statement and
the user's confirmed certificates only (FR-004, FR-012, Principle III).
"""

from typing import Any

import pytest
from conftest import TEST_PASSWORD
from document_helpers import add_confirmed_document
from wealth_statement import STATEMENT
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password
from app.documents.models import DocStatus, DocType
from app.main import app
from app.tax.summary import FakeSummariser
from app.wealth.router import get_wealth_summariser

pytestmark = pytest.mark.anyio

URL = "/api/wealth/2025-26"
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "72000"}
BANK = {"profit_amount": "50000", "tax_withheld": "10000"}


async def certificates(db: AsyncSession, user: User) -> None:
    """The example's salary and bank certificates, confirmed."""
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    await add_confirmed_document(db, user.id, DocType.BANK_PROFIT_CERTIFICATE, BANK)


async def test_logged_out_is_refused(client: AsyncClient) -> None:
    """Fails if anyone can read or write a wealth statement without logging in."""
    assert (await client.get(URL)).status_code == 401
    assert (await client.put(URL, json=STATEMENT)).status_code == 401


@pytest.mark.usefixtures("logged_in_user")
async def test_a_year_without_rates_is_404(client: AsyncClient) -> None:
    """Fails if a tax year the app doesn't support is answered."""
    assert (await client.get("/api/wealth/2024-25")).status_code == 404
    assert (await client.put("/api/wealth/2024-25", json=STATEMENT)).status_code == 404


@pytest.mark.usefixtures("logged_in_user")
async def test_a_statement_never_saved_is_empty_and_not_ready(client: AsyncClient) -> None:
    """Fails if a new user gets an error, figures, or no label."""
    body = (await client.get(URL)).json()

    assert body["statement"]["assets"] == [] and body["statement"]["saved_at"] is None
    assert body["result"]["not_ready_reason"] == "needs_previous_net_assets"
    assert body["result"]["message"]
    assert body["result"]["net_assets"] is None and body["result"]["steps"] == []
    assert body["certificates_changed"] is False
    assert body["label"] == LABEL


async def test_save_then_read_reconciles_the_signed_off_example(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a field doesn't round-trip, or the result differs from the hand working."""
    await certificates(db, logged_in_user)

    saved = await client.put(URL, json=STATEMENT)
    body = (await client.get(URL)).json()

    assert saved.status_code == 200
    assert saved.json()["result"] == body["result"]
    statement = body["statement"]
    for key, value in STATEMENT.items():
        if key == "liabilities":
            assert statement[key] == value
        else:
            assert statement[key] == value, key
    assert statement["saved_at"] is not None
    result = body["result"]
    assert result["not_ready_reason"] is None
    assert (result["net_assets"], result["increase"]) == ("2550000", "450000")
    assert (result["inflows"], result["outflows"]) == ("2050000", "1600000")
    assert (result["unreconciled"], result["direction"]) == ("0", "reconciled")
    assert [step["form_line"] for step in result["steps"]][-1] == "703000"
    assert result["where_to_look"] == []
    assert body["label"] == LABEL


async def test_auto_filled_lines_come_from_confirmed_certificates_and_name_them(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a certificate line is wrong, editable through the API, or doesn't say which
    certificate it came from (FR-004)."""
    await certificates(db, logged_in_user)

    lines = {line["label"]: line for line in (await client.get(URL)).json()["auto_filled"]}

    taxable = lines["Taxable salary"]
    assert (taxable["line"], taxable["amount"]) == ("7031", "1800000")
    assert taxable["certificates"] and taxable["certificates"][0].startswith("Salary certificate")
    exempt = lines["Exempt part of salary (gross - taxable)"]
    assert (exempt["line"], exempt["amount"], exempt["provisional"]) == ("7032", "200000", True)
    profit = lines["Bank profit"]
    assert (profit["line"], profit["amount"]) == ("7033", "50000")
    assert profit["certificates"][0].startswith("Bank profit certificate")
    tax = lines["Tax deducted and withheld at source (outflow)"]
    assert (tax["line"], tax["amount"]) == (None, "82000")
    assert len(tax["certificates"]) == 2


@pytest.mark.usefixtures("logged_in_user")
async def test_an_unconfirmed_or_another_users_certificate_is_never_counted(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if another user's figures reach this statement (FR-016, Principle III)."""
    other = User(email="other@example.com", password_hash=hash_password("other-pass"))
    db.add(other)
    await db.commit()
    await add_confirmed_document(db, other.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.put(URL, json=STATEMENT)

    body = (await client.get(URL)).json()

    assert body["result"]["not_ready_reason"] == "no_confirmed_salary_certificate"
    assert all(line["certificates"] == [] for line in body["auto_filled"])


@pytest.mark.parametrize(
    "change",
    [
        {"inheritance": "-1"},
        {"gifts_given": "100.50"},
        {"assets": [{"category": "yacht", "description": "Boat", "amount": "1"}]},
        {"assets": [{"category": "bank_account", "description": "", "amount": "1"}]},
    ],
)
@pytest.mark.usefixtures("logged_in_user")
async def test_invalid_entries_are_422_and_nothing_is_saved(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    """Fails if an invalid statement is saved, or the error repeats what was sent."""
    response = await client.put(URL, json={**STATEMENT, **change})

    assert response.status_code == 422
    assert "Boat" not in response.text and "100.50" not in response.text
    assert (await client.get(URL)).json()["statement"]["saved_at"] is None


@pytest.mark.usefixtures("logged_in_user")
async def test_saving_again_replaces_the_whole_statement(client: AsyncClient) -> None:
    """Fails if rows from an earlier save survive a replace (research R8)."""
    await client.put(URL, json=STATEMENT)
    await client.put(URL, json={**STATEMENT, "assets": [], "expenses": {"rent": "1"}})

    statement = (await client.get(URL)).json()["statement"]

    assert statement["assets"] == [] and statement["expenses"] == {"rent": "1"}


@pytest.mark.usefixtures("logged_in_user")
async def test_non_json_save_is_refused(client: AsyncClient) -> None:
    """Fails if a save accepts a form post (002 research R3: JSON only)."""
    assert (await client.put(URL, data={"previous_net_assets": "1"})).status_code == 415


# Task T020: the certificate-change notice (research R7, FR-013).


async def test_the_notice_appears_when_certificates_change_and_clears_on_save(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a certificate added or deleted since the last save goes unnoticed, or the notice
    stays after the user saves again."""
    await certificates(db, logged_in_user)
    await client.put(URL, json=STATEMENT)
    assert (await client.get(URL)).json()["certificates_changed"] is False

    added = await add_confirmed_document(
        db, logged_in_user.id, DocType.BANK_PROFIT_CERTIFICATE, BANK
    )
    assert (await client.get(URL)).json()["certificates_changed"] is True

    await client.put(URL, json=STATEMENT)
    assert (await client.get(URL)).json()["certificates_changed"] is False

    deleted = await client.request("DELETE", f"/api/documents/{added.id}", json={})
    assert deleted.status_code == 204
    assert (await client.get(URL)).json()["certificates_changed"] is True


# Backend review findings.


async def test_another_user_never_sees_or_changes_my_statement(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if one user's statement is visible to, or overwritten by, another (FR-016)."""
    del logged_in_user
    await client.put(URL, json=STATEMENT)
    await client.post("/api/auth/logout", json={})
    other = User(email="other@example.com", password_hash=hash_password("other-pass"))
    db.add(other)
    await db.commit()
    login = await client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    assert login.status_code == 200

    theirs = (await client.get(URL)).json()
    assert theirs["statement"]["saved_at"] is None and theirs["statement"]["assets"] == []
    assert theirs["result"]["not_ready_reason"] == "needs_previous_net_assets"
    await client.put(URL, json={**STATEMENT, "assets": []})

    await client.post("/api/auth/logout", json={})
    await client.post(
        "/api/auth/login", json={"email": "demo@example.com", "password": TEST_PASSWORD}
    )
    mine = (await client.get(URL)).json()
    assert len(mine["statement"]["assets"]) == 2


async def test_a_certificate_not_yet_confirmed_is_never_counted(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a figure the user hasn't confirmed reaches the statement (Principle III)."""
    document = await add_confirmed_document(
        db, logged_in_user.id, DocType.SALARY_CERTIFICATE, SALARY
    )
    document.status = DocStatus.NEEDS_REVIEW
    await db.commit()

    body = (await client.put(URL, json=STATEMENT)).json()

    assert body["result"]["not_ready_reason"] == "no_confirmed_salary_certificate"
    assert all(line["certificates"] == [] for line in body["auto_filled"])


async def test_a_certificate_is_named_by_its_type_and_upload_time(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the name loses the upload time (research R11), or two certificates uploaded in
    the same minute can't be told apart (seconds are shown)."""
    document = await add_confirmed_document(
        db, logged_in_user.id, DocType.SALARY_CERTIFICATE, SALARY
    )

    line = (await client.get(URL)).json()["auto_filled"][0]

    expected = f"Salary certificate uploaded {document.created_at:%Y-%m-%d %H:%M:%S} UTC"
    assert line["certificates"] == [expected]


@pytest.mark.usefixtures("logged_in_user")
async def test_a_refused_category_or_amount_is_never_echoed(client: AsyncClient) -> None:
    """Fails if a 422 repeats what was sent (security rule: errors carry no input)."""
    for change in (
        {"assets": [{"category": "yacht", "description": "Boat", "amount": "1"}]},
        {"inheritance": "-12345"},
    ):
        response = await client.put(URL, json={**STATEMENT, **change})
        assert response.status_code == 422
        assert "yacht" not in response.text and "-12345" not in response.text


@pytest.mark.usefixtures("logged_in_user")
async def test_minus_zero_is_saved_and_shown_as_zero(client: AsyncClient) -> None:
    """Fails if "-0" is echoed back as a negative-looking amount."""
    saved = (await client.put(URL, json={**STATEMENT, "inheritance": "-0"})).json()

    assert saved["statement"]["inheritance"] == "0"


class RecordingSummariser:  # pylint: disable=too-few-public-methods
    """Counts how often the AI would be asked."""

    def __init__(self) -> None:
        self.calls = 0

    async def write(self, breakdown: str) -> str | None:
        """Count the call; write nothing."""
        del breakdown
        self.calls += 1
        return None


async def test_reading_and_saving_never_wait_for_the_summary(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if reading or saving asks the AI, or still carries a summary (feature 001, US6)."""
    await certificates(db, logged_in_user)
    recorder = RecordingSummariser()
    app.dependency_overrides[get_wealth_summariser] = lambda: recorder
    try:
        saved = (await client.put(URL, json=STATEMENT)).json()
        read = (await client.get(URL)).json()
    finally:
        app.dependency_overrides.pop(get_wealth_summariser, None)

    assert recorder.calls == 0
    assert "summary" not in saved["result"] and "summary" not in read["result"]
    assert read["result"]["direction"] == "reconciled"


async def test_the_summary_request_returns_a_checked_summary(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a safe summary is lost between the check and the response (service wiring)."""
    await certificates(db, logged_in_user)
    await client.put(URL, json=STATEMENT)
    text = "Your wealth statement reconciles: inflows of Rs 2,050,000 explain the change."
    app.dependency_overrides[get_wealth_summariser] = lambda: FakeSummariser(text)
    try:
        response = await client.get(URL + "/summary")
    finally:
        app.dependency_overrides.pop(get_wealth_summariser, None)

    assert response.status_code == 200
    assert response.json() == {"summary": text}


@pytest.mark.usefixtures("logged_in_user")
async def test_a_not_ready_statement_has_no_summary(client: AsyncClient) -> None:
    """Fails if a statement that can't be reconciled yet gets an AI summary."""
    app.dependency_overrides[get_wealth_summariser] = lambda: FakeSummariser("Rs 1")
    try:
        response = await client.get(URL + "/summary")
    finally:
        app.dependency_overrides.pop(get_wealth_summariser, None)

    assert response.json() == {"summary": None}


@pytest.mark.usefixtures("logged_in_user")
async def test_the_summary_request_needs_a_known_year(client: AsyncClient) -> None:
    """Fails if the summary answers for a year without rates."""
    assert (await client.get("/api/wealth/2019-20/summary")).status_code == 404


async def test_amounts_read_back_from_the_database_are_plain_rupees(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if an amount reloaded from the database is sent as "1.35E+6" (the driver's form for
    whole-rupee columns), which the page and the PDF then show as is. Found by 008's PDF check:
    the tests had only seen amounts still cached in the session."""
    await certificates(db, logged_in_user)
    await client.put(URL, json=STATEMENT)
    db.expire_all()  # read everything back from the database, as a later request would

    statement = (await client.get(URL)).json()["statement"]

    assert [row["amount"] for row in statement["assets"]] == ["1350000", "1400000"]
    assert statement["liabilities"][0]["amount"] == "200000"
    assert statement["previous_net_assets"] == "2100000"
    assert statement["expenses"]["rent"] == "600000"
