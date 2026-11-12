"""Guardrail: the AI never changes a figure (constitution Principle I; feature 008, task T011,
research R5).

Every AI client in the app is replaced by one that answers with made-up numbers. The tax, wealth
and guided-filing results must still equal the hand-worked, signed-off examples to the rupee,
and the made-up numbers must never be shown.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import a_corpus
from sqlalchemy.ext.asyncio import AsyncSession
from wealth_statement import STATEMENT

from app.auth.models import User
from app.documents.models import DocType
from app.main import app
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser
from app.wealth.router import get_wealth_summariser
from app.workflow.client import FakeAgentClient, Script
from app.workflow.router import get_agent_client

pytestmark = pytest.mark.anyio

TESTS = Path(__file__).resolve().parent.parent
MADE_UP = "Rs 987,654"
TAX_FIGURES = (
    "salary_tax",
    "surcharge",
    "profit_tax",
    "salary_balance",
    "profit_balance",
    "non_atl_extra_withheld",
)
WEALTH_FIGURES = ("net_assets", "increase", "inflows", "outflows", "unreconciled", "direction")


def example(path: str, example_id: str) -> dict[str, Any]:
    """A signed-off worked example (004's or 005's)."""
    examples = yaml.safe_load((TESTS / path).read_text(encoding="utf-8"))["examples"]
    found: dict[str, Any] = next(e for e in examples if e["id"] == example_id)
    assert found["signed_off_by"] and found["signed_off_date"], "only signed-off examples"
    return found


TAX = example("tax/worked_examples.yaml", "two-salary-and-two-bank-certificates")
WEALTH = example("wealth/worked_examples.yaml", "reconciled")


@pytest.fixture
def lying_ai() -> Iterator[FakeAgentClient]:
    """Every AI the app uses answers with a number that is in no result."""
    agents = FakeAgentClient(
        {
            "document": Script(reply={"message": f"You owe {MADE_UP}."}),
            "validation": Script(reply={"message": f"Your taxable salary is {MADE_UP}."}),
            "research": Script(
                reply={"note": f"The rate is 99% above {MADE_UP} (P1).", "citations": ["P1"]}
            ),
        }
    )
    app.dependency_overrides[get_summariser] = lambda: FakeSummariser(f"Your tax is {MADE_UP}.")
    app.dependency_overrides[get_wealth_summariser] = lambda: FakeSummariser(
        f"{MADE_UP} is unexplained."
    )
    app.dependency_overrides[get_agent_client] = lambda: agents
    yield agents
    for dependency in (get_summariser, get_wealth_summariser, get_agent_client):
        app.dependency_overrides.pop(dependency, None)


async def tax_certificates(db: AsyncSession, user: User) -> None:
    """The tax example's certificates, confirmed."""
    for salary in TAX["inputs"]["salary_certificates"]:
        await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, salary)
    for bank in TAX["inputs"]["bank_certificates"]:
        await add_confirmed_document(db, user.id, DocType.BANK_PROFIT_CERTIFICATE, bank)


def tax_figures(result: dict[str, Any]) -> dict[str, Any]:
    """The result's figures, as the example writes them."""
    return {name: result[name] for name in TAX_FIGURES}


@pytest.mark.usefixtures("lying_ai")
async def test_the_tax_result_is_the_worked_example_whatever_the_ai_says(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if an AI summary changes a tax figure, or its made-up number is shown."""
    assert TAX["inputs"]["atl"] is True  # the profile fixture is on the ATL
    await tax_certificates(db, user_with_profile)

    result = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()
    summary = (await client.get(f"/api/tax/{PROFILE_YEAR}/summary")).json()

    assert result["blocked_reason"] is None
    assert tax_figures(result) == {name: TAX["expected"][name] for name in TAX_FIGURES}
    assert summary == {"summary": None}


@pytest.mark.usefixtures("lying_ai")
async def test_the_wealth_result_is_the_worked_example_whatever_the_ai_says(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if an AI summary changes a wealth figure, or its made-up number is shown."""
    for salary in WEALTH["inputs"]["salary_certificates"]:
        figures = {k: v for k, v in salary.items() if k != "file"}
        await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, figures)
    for bank in WEALTH["inputs"]["bank_certificates"]:
        figures = {k: v for k, v in bank.items() if k != "file"}
        await add_confirmed_document(
            db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, figures
        )
    await client.put(f"/api/wealth/{PROFILE_YEAR}", json=STATEMENT)

    result = (await client.get(f"/api/wealth/{PROFILE_YEAR}")).json()["result"]
    summary = (await client.get(f"/api/wealth/{PROFILE_YEAR}/summary")).json()

    assert result["not_ready_reason"] is None
    assert {name: result[name] for name in WEALTH_FIGURES} == {
        name: WEALTH["expected"][name] for name in WEALTH_FIGURES
    }
    assert summary == {"summary": None}


@pytest.mark.usefixtures("lying_ai")
async def test_the_guided_result_is_the_worked_example_whatever_the_agents_say(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if an agent's made-up number reaches a guided-filing step or changes the result."""
    await a_corpus(db)
    await tax_certificates(db, user_with_profile)

    run = (await client.post("/api/workflow/start", json={})).json()
    await client.post("/api/workflow/approve", json={"fingerprint": run["fingerprint"]})
    result = (await client.get("/api/workflow/result")).json()

    assert run["validation"]["fallback"] is True and run["research"]["fallback"] is True
    shown = f"{run} {result}"
    assert "987,654" not in shown and "987654" not in shown
    assert tax_figures(result) == {name: TAX["expected"][name] for name in TAX_FIGURES}
