"""Telemetry never records user content (feature 008, task T018; FR-012, SC-005, Principle V).

After a synthetic run through the app (upload, tax, ask, guided filing), no span's name or
attribute holds the user's email, a user or document id, a figure, a question, a prompt or a
reply, or SQL text.
"""

from typing import Any

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document, make_pdf, upload
from httpx2 import AsyncClient
from rag_helpers import QUESTION, a_corpus
from sqlalchemy.ext.asyncio import AsyncSession
from telemetry_helpers import Spans

from app.auth.models import User
from app.documents.models import DocType
from app.main import app
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser
from app.workflow.client import FakeAgentClient, Script
from app.workflow.router import get_agent_client

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2345678", "taxable_salary": "1876543", "tax_deducted": "76543"}
SUMMARY = "Your salary tax works out from the breakdown above."
AGENT_TEXT = "Your certificates look complete and consistent."


def everything_recorded(spans: Spans) -> str:
    """Every span name, attribute key and attribute value, as one text."""
    parts: list[Any] = []
    for span in spans.all():
        parts.append(span.name)
        for key, value in (span.attributes or {}).items():
            parts += [key, value]
        for event in span.events:
            parts.append(event.name)
            parts += list((event.attributes or {}).items())
    return "\n".join(str(part) for part in parts)


async def test_no_span_holds_user_content(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, spans: Spans
) -> None:
    """Fails if telemetry records anything that identifies the user or what they sent or got."""
    app.dependency_overrides[get_summariser] = lambda: FakeSummariser(SUMMARY)
    app.dependency_overrides[get_agent_client] = lambda: FakeAgentClient(
        {
            "document": Script(reply={"message": AGENT_TEXT}),
            "validation": Script(reply={"message": AGENT_TEXT}),
            "research": Script(
                calls=[("search_tax_documents", {"query": QUESTION})],
                reply={"note": "Employers deduct tax (P1).", "citations": ["P1"]},
            ),
        }
    )
    await a_corpus(db)
    uploaded = (await upload(client, make_pdf())).json()
    document = await add_confirmed_document(
        db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY
    )
    tax = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()
    await client.get(f"/api/tax/{PROFILE_YEAR}/summary")
    await client.get(f"/api/documents/{document.id}")
    await client.post("/api/ask", json={"question": QUESTION})
    await client.post("/api/workflow/start", json={})

    recorded = everything_recorded(spans)
    database = [s for s in spans.all() if (s.attributes or {}).get("db.system.name")]
    assert database, "expected database spans to check"
    forbidden = {
        "email": user_with_profile.email,
        "user id": str(user_with_profile.id),
        "uploaded document id": str(uploaded["id"]),
        "document id": str(document.id),
        "taxable salary": "1876543",
        "tax deducted": "76543",
        "salary tax": str(tax["salary_tax"]),
        "question": QUESTION,
        "summary": SUMMARY,
        "agent text": AGENT_TEXT,
        "SQL": "FROM ",
        "SQL parameters": "$1",
    }
    for what, text in forbidden.items():
        assert text not in recorded, what
