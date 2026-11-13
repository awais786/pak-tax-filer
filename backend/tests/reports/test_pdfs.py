"""PDF exports (feature 008, task T004; contracts/pdf-and-telemetry.md, FR-001 to FR-007).

Each PDF is read back with pypdf: the practitioner label, "Demo data only." and the validation
status must be on every page, the figures must equal the JSON result, and no AI-written text may
appear. Blocked, not-ready and unapproved results export nothing.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import io
from collections.abc import Iterator

import pypdf
import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from wealth_statement import STATEMENT
from httpx2 import AsyncClient, Response
from rag_helpers import QUESTION, a_corpus
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocType
from app.main import app
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser
from app.workflow.client import FakeAgentClient, Script
from app.workflow.router import get_agent_client
from app.wealth.router import get_wealth_summariser

pytestmark = pytest.mark.anyio

LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
AI_TEXT = "WRITTEN-BY-THE-AI"


def pages(response: Response) -> list[str]:
    """Each page's text, whitespace removed (PDF text extraction breaks lines anywhere)."""
    reader = pypdf.PdfReader(io.BytesIO(response.content))
    return ["".join((page.extract_text() or "").split()) for page in reader.pages]


def squash(text: str) -> str:
    """Text as `pages` compares it."""
    return "".join(text.split())


def assert_pdf(response: Response, filename: str) -> None:
    """A PDF download with this file name."""
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'


@pytest.fixture
def ai_writes_text() -> Iterator[None]:
    """Summaries the AI would write; none may reach a PDF (FR-005)."""
    app.dependency_overrides[get_summariser] = lambda: FakeSummariser(AI_TEXT)
    app.dependency_overrides[get_wealth_summariser] = lambda: FakeSummariser(AI_TEXT)
    yield
    app.dependency_overrides.pop(get_summariser, None)
    app.dependency_overrides.pop(get_wealth_summariser, None)


# ---- Tax ----


@pytest.mark.usefixtures("ai_writes_text")
async def test_the_tax_pdf_has_the_banner_status_and_the_results_figures(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the tax PDF lacks the label or status, or its figures differ from the JSON."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    result = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    response = await client.get(f"/api/tax/{PROFILE_YEAR}/pdf")

    assert_pdf(response, f"tax-{PROFILE_YEAR}.pdf")
    text = pages(response)
    for page in text:
        assert squash(LABEL) in page and squash("Demo data only.") in page
        assert squash("All figures are from your confirmed certificates") in page
        assert squash("No warnings") in page
    document = "".join(text)
    for step in result["steps"]:
        assert squash(step["description"]) in document
        assert squash(step["rule_location"]) in document
    assert squash("Rs 72,000") in document  # salary tax
    assert AI_TEXT not in document


async def test_a_blocked_tax_result_exports_nothing(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if a result 004 refuses (no confirmed salary certificate) can be exported."""
    del user_with_profile
    blocked = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    response = await client.get(f"/api/tax/{PROFILE_YEAR}/pdf")

    assert response.status_code == 409
    assert response.json() == {"detail": blocked["message"]}


# ---- Wealth ----


async def test_every_page_of_a_long_wealth_pdf_has_the_banner(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a page past the first loses the label or status (Principle IV)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    rows = [
        {"category": "other_asset", "description": f"Asset {i}", "amount": "1000"}
        for i in range(80)
    ]
    await client.put(f"/api/wealth/{PROFILE_YEAR}", json={**STATEMENT, "assets": rows})

    response = await client.get(f"/api/wealth/{PROFILE_YEAR}/pdf")

    assert_pdf(response, f"wealth-{PROFILE_YEAR}.pdf")
    text = pages(response)
    assert len(text) > 1
    for page in text:
        assert squash(LABEL) in page and squash("Demo data only.") in page
        assert squash("Salary figures are from your confirmed certificates") in page


@pytest.mark.usefixtures("ai_writes_text")
async def test_the_wealth_pdf_has_the_reconciliation_as_computed(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the wealth PDF's figures or steps differ from the JSON, or AI text appears."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    body = (await client.put(f"/api/wealth/{PROFILE_YEAR}", json=STATEMENT)).json()

    response = await client.get(f"/api/wealth/{PROFILE_YEAR}/pdf")

    assert_pdf(response, f"wealth-{PROFILE_YEAR}.pdf")
    document = "".join(pages(response))
    for step in body["result"]["steps"]:
        assert squash(step["description"]) in document
    assert squash("Car loan") in document and squash("Savings account") in document
    assert AI_TEXT not in document


async def test_a_wealth_statement_not_ready_exports_nothing(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if a statement 005 can't reconcile yet (never saved) can be exported."""
    del user_with_profile
    body = (await client.get(f"/api/wealth/{PROFILE_YEAR}")).json()

    response = await client.get(f"/api/wealth/{PROFILE_YEAR}/pdf")

    assert response.status_code == 409
    assert response.json() == {"detail": body["result"]["message"]}


# ---- Guided filing ----


@pytest.fixture
def research_agent() -> Iterator[None]:
    """A research agent that cites §149(1); its note (AI text) must stay out of the PDF."""
    fake = FakeAgentClient(
        {
            "research": Script(
                calls=[("search_tax_documents", {"query": QUESTION})],
                reply={"note": f"{AI_TEXT} employers deduct tax (P1).", "citations": ["P1"]},
            )
        }
    )
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield
    app.dependency_overrides.pop(get_agent_client, None)


@pytest.mark.usefixtures("research_agent")
async def test_an_approved_guided_run_exports_with_its_approval_and_passages(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the guided run's PDF lacks the approval line or cited passages, or shows the
    research note the AI wrote."""
    await a_corpus(db)
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    run = (await client.post("/api/workflow/start", json={})).json()
    assert run["research"]["fallback"] is False
    await client.post("/api/workflow/approve", json={"fingerprint": run["fingerprint"]})

    response = await client.get("/api/workflow/result/pdf")

    assert_pdf(response, f"tax-{PROFILE_YEAR}.pdf")
    text = pages(response)
    for page in text:
        assert squash(LABEL) in page and squash("Approved by you on") in page
    document = "".join(text)
    assert squash("§149(1)") in document
    assert AI_TEXT not in document


async def test_an_unapproved_guided_run_exports_nothing(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a guided run waiting at the gate can be exported (Principle III)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.post("/api/workflow/start", json={})

    response = await client.get("/api/workflow/result/pdf")

    assert response.status_code == 409 and response.json() == {"detail": "Approval needed."}


# ---- Access ----


async def test_pdfs_need_a_login_and_a_profile(client: AsyncClient, logged_in_user: User) -> None:
    """Fails if a PDF can be had without logging in, or without a profile."""
    del logged_in_user
    paths = (
        f"/api/tax/{PROFILE_YEAR}/pdf",
        f"/api/wealth/{PROFILE_YEAR}/pdf",
        "/api/workflow/result/pdf",
    )
    for path in paths:
        assert (await client.get(path)).status_code == 409, path  # logged in, no profile
    await client.post("/api/auth/logout", json={})
    for path in paths:
        assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("kind", ["tax", "wealth"])
async def test_another_users_figures_are_never_exported(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, kind: str
) -> None:
    """Fails if one user's certificates could appear in another's PDF."""
    other = User(email="other-pdf@example.com", password_hash="not-a-real-hash")
    db.add(other)
    await db.flush()
    await add_confirmed_document(db, other.id, DocType.SALARY_CERTIFICATE, SALARY)
    del user_with_profile

    response = await client.get(f"/api/{kind}/{PROFILE_YEAR}/pdf")

    # The logged-in user has no certificate of their own: the other user's isn't used.
    assert response.status_code == 409
    assert "profile" not in response.json()["detail"].lower()


@pytest.mark.parametrize("kind", ["tax", "wealth"])
@pytest.mark.usefixtures("user_with_profile")
async def test_a_tax_year_without_rates_is_404(client: AsyncClient, kind: str) -> None:
    """Fails if a PDF is attempted for a year the app has no rates for."""
    response = await client.get(f"/api/{kind}/2019-20/pdf")

    assert response.status_code == 404
    assert response.json() == {"detail": "No rates for that tax year."}


async def test_an_approved_but_blocked_guided_run_exports_nothing(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a guided run approved for inputs 004 refuses to calculate (profit over the Rs 5
    million limit) can be exported with empty figures (FR-007)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await add_confirmed_document(
        db,
        user_with_profile.id,
        DocType.BANK_PROFIT_CERTIFICATE,
        {"profit_amount": "6000000", "tax_withheld": "0"},
    )
    run = (await client.post("/api/workflow/start", json={})).json()
    await client.post("/api/workflow/approve", json={"fingerprint": run["fingerprint"]})
    blocked = (await client.get("/api/workflow/result")).json()
    assert blocked["blocked_reason"] is not None

    response = await client.get("/api/workflow/result/pdf")

    assert response.status_code == 409 and response.json() == {"detail": blocked["message"]}
