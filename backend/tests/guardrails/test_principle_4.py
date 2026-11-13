"""Guardrail: honest, labelled output (constitution Principle IV; feature 008, task T013,
research R5).

The assistant answers only with checked citations and numbers, and refuses otherwise; the guided
run's law comes only from search; every result carries the practitioner label, and every page of
every PDF carries the banner.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import io
from collections.abc import Iterator

import pypdf
import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import QUESTION, TEXTS, a_corpus, reply
from sqlalchemy.ext.asyncio import AsyncSession
from wealth_statement import STATEMENT

from app.auth.models import User
from app.documents.models import DocType
from app.main import app
from app.rag.answer import FakeAnswerer, ModelAnswer
from app.rag.router import get_answerer
from app.workflow.client import FakeAgentClient, Script
from app.workflow.router import get_agent_client

pytestmark = pytest.mark.anyio

LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


def answering(model_reply: ModelAnswer) -> Iterator[None]:
    """The assistant's AI, replaced by one giving this reply."""
    app.dependency_overrides[get_answerer] = lambda: FakeAnswerer(model_reply)
    yield
    app.dependency_overrides.pop(get_answerer, None)


@pytest.fixture
def faithful_ai() -> Iterator[None]:
    """A reply citing the passage it uses, with no numbers of its own."""
    yield from answering(reply())


@pytest.fixture
def ai_with_a_scaled_number() -> Iterator[None]:
    """A reply whose "10m" is in no passage (004's limit, from the AI's memory)."""
    yield from answering(reply(answer="Employers deduct tax once salary passes Rs 10m."))


# ---- The assistant ----


@pytest.mark.usefixtures("faithful_ai", "logged_in_user")
async def test_an_answer_in_the_corpus_is_cited_and_labelled(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if a shown answer has no citation or no label."""
    await a_corpus(db)

    body = (await client.post("/api/ask", json={"question": QUESTION})).json()

    assert body["status"] == "answered"
    assert [c["location"] for c in body["citations"]] == ["§149(1)"]
    assert body["label"] == LABEL


@pytest.mark.usefixtures("ai_with_a_scaled_number", "logged_in_user")
async def test_a_number_the_passages_dont_have_is_refused_even_abbreviated(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if an answer with "10m" (a number no cited passage has) is shown."""
    await a_corpus(db)

    body = (await client.post("/api/ask", json={"question": QUESTION})).json()

    assert body["status"] == "not_covered" and body["citations"] == []
    assert "10m" not in body["answer"]


@pytest.mark.parametrize(
    "question",
    ["What is the sales tax on imported cars?", "کیا میری تنخواہ پر ٹیکس کٹتا ہے؟"],
    ids=["outside-the-corpus", "in-urdu"],
)
@pytest.mark.usefixtures("faithful_ai", "logged_in_user")
async def test_questions_outside_the_corpus_or_in_urdu_are_refused(
    client: AsyncClient, db: AsyncSession, question: str
) -> None:
    """Fails if the assistant answers what its English sources don't cover."""
    await a_corpus(db)

    body = (await client.post("/api/ask", json={"question": question})).json()

    assert body["status"] == "not_covered" and body["citations"] == []
    assert body["label"] == LABEL


# ---- The guided run's law ----


@pytest.mark.parametrize(
    ("citations", "shown"),
    [(["P1"], ["§149(1)"]), (["P1", "P9"], None)],
    ids=["cites-what-search-found", "cites-a-passage-search-never-found"],
)
async def test_the_guided_runs_law_comes_only_from_search(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    citations: list[str],
    shown: list[str] | None,
) -> None:
    """Fails if the research step shows a passage search didn't return, or keeps an agent's
    note that cites one (it falls back to the plain search result instead)."""
    fake = FakeAgentClient(
        {
            "research": Script(
                calls=[("search_tax_documents", {"query": QUESTION})],
                reply={
                    "note": f"Employers deduct tax ({', '.join(citations)}).",
                    "citations": citations,
                },
            )
        }
    )
    app.dependency_overrides[get_agent_client] = lambda: fake
    await a_corpus(db)
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)

    research = (await client.post("/api/workflow/start", json={})).json()["research"]

    locations = [p["location"] for p in research["passages"]]
    assert set(locations) <= set(TEXTS)
    if shown is None:
        assert research["fallback"] is True and "P9" not in research["note"]
    else:
        assert research["fallback"] is False and locations == shown


# ---- Labels and banners ----


async def results(client: AsyncClient, db: AsyncSession, user: User) -> dict[str, str]:
    """A user with every result available: tax, wealth and an approved guided run."""
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.put(f"/api/wealth/{PROFILE_YEAR}", json=STATEMENT)
    run = (await client.post("/api/workflow/start", json={})).json()
    await client.post("/api/workflow/approve", json={"fingerprint": run["fingerprint"]})
    return {
        "tax": f"/api/tax/{PROFILE_YEAR}",
        "wealth": f"/api/wealth/{PROFILE_YEAR}",
        "workflow": "/api/workflow/result",
    }


async def test_every_result_carries_the_label(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a tax, wealth or guided result reaches the user without the label."""
    for name, url in (await results(client, db, user_with_profile)).items():
        response = await client.get(url)
        assert response.status_code == 200, name
        assert response.json()["label"] == LABEL, name


async def test_a_blocked_result_carries_the_label_too(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if a result that couldn't be calculated drops the label."""
    assert user_with_profile

    body = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    assert body["blocked_reason"] == "no_confirmed_salary_certificate"
    assert body["label"] == LABEL


async def test_every_page_of_every_pdf_carries_the_banner(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if any page of the tax, wealth or guided PDF lacks the label or "Demo data only."."""
    for name, url in (await results(client, db, user_with_profile)).items():
        response = await client.get(f"{url}/pdf")
        assert response.status_code == 200, name
        pages = pypdf.PdfReader(io.BytesIO(response.content)).pages
        assert len(pages) >= 1, name
        for number, page in enumerate(pages, start=1):
            text = "".join((page.extract_text() or "").split())
            assert "".join(LABEL.split()) in text, f"{name} page {number}"
            assert "Demodataonly." in text, f"{name} page {number}"
