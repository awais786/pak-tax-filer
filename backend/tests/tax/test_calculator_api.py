"""POST /api/tax/calculator (feature 010, tasks T012, T017, T018;
specs/010-income-tax-engine/contracts/calculator-api.md).

The user types amounts; tax year and ATL status come from their profile; nothing is stored,
logged or sent to an AI (FR-003).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from httpx2 import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from telemetry_helpers import Spans

from app.auth.models import User
from app.profile.service import save_profile
from app.tax.calculator import NOT_COVERED

pytestmark = pytest.mark.anyio

URL = "/api/tax/calculator"
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
# Every field of the contract's response, always present (calculator-api.md).
FIELDS = set(
    "tax_year blocked_reason message incomes taxable_income salary_share table slab_tax "
    "surcharge dividend_tax profit_tax total_tax effective_rate monthly bonus_impact "
    "filer_comparison on_atl steps not_covered label".split()
)
LEAD = {"salary_monthly": "250000", "rent_monthly": "140000"}
# The citation for figures worked from the lines above, which no rule sets (review L4).
DERIVED = "Worked out from the lines above (not a separate rule)"


@contextmanager
def writes(db: AsyncSession) -> Iterator[list[str]]:
    """Every INSERT, UPDATE or DELETE sent to the database inside the block."""
    seen: list[str] = []
    bind = db.sync_session.get_bind()

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            seen.append(statement)

    event.listen(bind, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(bind, "before_cursor_execute", record)


async def test_signed_out_is_refused(client: AsyncClient) -> None:
    """Fails if the calculator answers without a session (401)."""
    assert (await client.post(URL, json=LEAD)).status_code == 401


async def test_no_profile_is_refused(client: AsyncClient, logged_in_user: User) -> None:
    """Fails if a user without a taxpayer profile gets a result (409, FR-011)."""
    del logged_in_user
    assert (await client.post(URL, json=LEAD)).status_code == 409


async def test_a_form_post_is_refused(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a non-JSON body is accepted (415, require_json)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    response = await client.post(
        URL,
        content="salary_monthly=250000",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 415


@pytest.mark.parametrize(
    "amount", ["-1", "100.001", "12345678901234", "abc", "1e5", "1_000", "٢٥٠"]
)
async def test_an_invalid_amount_is_refused_without_echoing_it(
    client: AsyncClient, db: AsyncSession, logged_in_user: User, amount: str
) -> None:
    """Fails if a negative amount, more than 2 decimal places, more than 13 digits before the
    point, or a non-number is accepted, or if the error repeats the value (422)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    response = await client.post(URL, json={"salary_monthly": amount})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "salary_monthly"
    assert amount not in response.text


async def test_a_json_number_is_refused(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if money arrives as a JSON number, not a decimal string (docs/api-conventions.md;
    backend review M4)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    response = await client.post(URL, json={"salary_monthly": 250000.5})

    assert response.status_code == 422


async def test_the_largest_amount_is_accepted(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if 13 digits and 2 decimal places, the contract's limit, is refused."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    response = await client.post(URL, json={"dividends": "9999999999999.99"})

    assert response.status_code == 200


async def test_the_leads_example_has_every_contract_field(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the result's shape or figures differ from the contract (money as strings)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    body = (await client.post(URL, json=LEAD)).json()

    assert set(body) == FIELDS
    assert body["tax_year"] == "2025-26"
    assert body["blocked_reason"] is None
    assert body["taxable_income"] == "4344000"
    assert body["salary_share"] == "69.06"
    assert body["table"] == "non_salaried"
    assert body["slab_tax"] == "1107600"
    assert body["total_tax"] == "1107600"
    assert body["effective_rate"] == "23.7"
    assert body["monthly"] == {"salary_tax": "25000", "take_home": "225000"}
    assert body["bonus_impact"] is None
    assert body["filer_comparison"] == []
    assert body["incomes"] == [
        {
            "source": "salary",
            "yearly_amount": "3000000",
            "taxable_amount": "3000000",
            "treatment": "slab",
        },
        {
            "source": "rent",
            "yearly_amount": "1680000",
            "taxable_amount": "1344000",
            "treatment": "slab",
        },
    ]
    assert body["not_covered"] == list(NOT_COVERED)
    assert body["label"] == LABEL
    assert body["on_atl"] is True
    # Money in steps reads like every other amount: "1344000", never "1344000.00".
    assert [step["result"] for step in body["steps"][:3]] == ["3000000", "1344000", "4344000"]


async def test_every_step_cites_its_rule_and_effective_date(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a breakdown line doesn't name the Ordinance, its pages and the date its rule
    applies from (FR-008, SC-002)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    body = (await client.post(URL, json={**LEAD, "bonus": "100000", "dividends": "50000"})).json()

    assert body["steps"]
    for step in body["steps"]:
        if step["rule_location"] == DERIVED:
            assert step["description"].startswith(("Effective rate", "Your bonus"))
            continue
        assert "Income Tax Ordinance, 2001" in step["rule_location"]
        assert "PDF p." in step["rule_location"]
        assert step["rule_location"].endswith("effective 2025-07-01")
        assert step["description"]
        assert step["result"]


async def test_atl_status_comes_from_the_profile(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the comparison ignores the profile's ATL status, or a field in the body can
    change it (FR-011)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=False)
    body = (await client.post(URL, json={"dividends": "1000000", "atl": True})).json()

    assert body["dividend_tax"] == "150000"
    assert body["on_atl"] is False
    assert body["filer_comparison"] == [
        {
            "source": "dividends",
            "your_rate": "30",
            "other_rate": "15",
            "your_deduction": "300000",
            "other_deduction": "150000",
            "difference": "150000",
        }
    ]


@pytest.mark.parametrize(
    ("body", "reason"),
    [({}, "no_income"), ({"bank_profit": "5000001"}, "profit_over_limit")],
)
async def test_a_refusal_has_a_reason_and_no_figures(
    client: AsyncClient, db: AsyncSession, logged_in_user: User, body: dict[str, str], reason: str
) -> None:
    """Fails if a refused case shows any figure, or lacks its message, the not-covered list or
    the label (SC-005)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    result = (await client.post(URL, json=body)).json()

    assert set(result) == FIELDS
    assert result["blocked_reason"] == reason
    assert result["message"]
    # Every figure: all fields except the text, the lists and the profile flag.
    words = {"tax_year", "blocked_reason", "message", "not_covered", "label", "on_atl"}
    figures = sorted(FIELDS - words - {"incomes", "steps", "filer_comparison"})
    for name in figures:
        assert result[name] is None, name
    assert result["incomes"] == result["steps"] == result["filer_comparison"] == []
    assert result["not_covered"] == list(NOT_COVERED)
    assert result["label"] == LABEL


async def test_nothing_is_stored_logged_or_traced(
    client: AsyncClient,
    db: AsyncSession,
    logged_in_user: User,
    caplog: pytest.LogCaptureFixture,
    spans: Spans,
) -> None:
    """Fails if a calculation writes to the database, or a typed amount reaches the logs or a
    span's attributes (FR-003)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    typed = {"salary_monthly": "271828", "rent_monthly": "31415", "dividends": "16180"}
    caplog.set_level(logging.DEBUG)

    with writes(db) as statements:
        response = await client.post(URL, json=typed)

    assert response.status_code == 200
    assert not statements
    logged = caplog.text
    traced = " ".join(str(span.attributes) for span in spans.all())
    for amount in typed.values():
        assert amount not in logged
        assert amount not in traced


async def test_the_steps_say_why_in_words(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the breakdown doesn't say the table, that dividends sit outside taxable income,
    or calls a bonus that lowers the tax an addition (US2 scenario 3; backend review M1, L6)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    lead = (await client.post(URL, json={**LEAD, "dividends": "10000"})).json()
    cliff = (
        await client.post(
            URL, json={"salary_monthly": "300000", "bonus": "1", "rent_monthly": "125000"}
        )
    ).json()

    lead_text = " ".join(step["description"] for step in lead["steps"])
    assert "does not exceed 75%: the non-salaried table applies" in lead_text
    assert "outside" in lead_text
    assert cliff["bonus_impact"] == "-429000"
    cliff_text = " ".join(step["description"] for step in cliff["steps"])
    assert "lowers the total tax by Rs 429,000" in cliff_text
    assert "just over 75%" in cliff_text
    assert "adds -" not in cliff_text


async def test_the_table_step_cites_the_75_percent_rule_and_no_bonus_says_none(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the step deciding the table cites a slab row instead of the 75% rule (clause (2)),
    or a salary without a bonus reads "+ bonus Rs 0" (T024 browser check)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=True)
    body = (await client.post(URL, json=LEAD)).json()

    salary_step, _property_step, table_step = body["steps"][:3]
    assert "bonus" not in salary_step["description"].split("=")[0]
    assert "clause (2)" in table_step["rule_location"]
    assert "75% of taxable income" in table_step["rule_location"]
