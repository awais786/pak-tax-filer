"""Guardrail: AI-extracted figures count only after the user confirms them, and the guided run
stops for approval (constitution Principle III; feature 008, task T012, research R5).

The user has one confirmed salary certificate and one the AI read but nobody confirmed. Every
place that calculates (the tax page, the wealth statement, the MCP tool and the guided run's
gate) must use the confirmed one only; the guided result and its PDF need an approval.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import json
from typing import Any

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from mcp import Client
from rag_helpers import sessions_of
from sqlalchemy.ext.asyncio import AsyncSession
from wealth_statement import STATEMENT

from app.auth.models import User
from app.documents.models import DocStatus, DocType
from app.mcp_server.server import build_server
from app.rag.embed import FakeEmbedder
from app.tokens.service import create_token

pytestmark = pytest.mark.anyio

CONFIRMED = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
UNCONFIRMED = {"gross_salary": "9000000", "taxable_salary": "8000000", "tax_deducted": "1000"}
# Salary tax on the confirmed Rs 1,800,000 alone: row 3, 6,000 + 11% of 600,000.
SALARY_TAX = "72000"


@pytest.fixture
async def two_certificates(db: AsyncSession, user_with_profile: User) -> User:
    """One confirmed salary certificate and one the AI extracted that awaits review."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, CONFIRMED)
    waiting = await add_confirmed_document(
        db, user_with_profile.id, DocType.SALARY_CERTIFICATE, UNCONFIRMED
    )
    waiting.status = DocStatus.NEEDS_REVIEW
    for field in waiting.fields:
        field.confirmed = False
    await db.commit()
    return user_with_profile


async def test_the_tax_page_counts_only_the_confirmed_certificate(
    client: AsyncClient, two_certificates: User
) -> None:
    """Fails if the unconfirmed certificate's figures reach GET /api/tax."""
    assert two_certificates

    result = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    assert result["blocked_reason"] is None
    assert result["salary_tax"] == SALARY_TAX and result["salary_credit"] == "75000"


async def test_the_wealth_statement_counts_only_the_confirmed_certificate(
    client: AsyncClient, two_certificates: User
) -> None:
    """Fails if the unconfirmed certificate's figures reach GET /api/wealth."""
    assert two_certificates
    await client.put(f"/api/wealth/{PROFILE_YEAR}", json=STATEMENT)

    body = (await client.get(f"/api/wealth/{PROFILE_YEAR}")).json()

    lines = {line["label"]: line for line in body["auto_filled"]}
    assert lines["Taxable salary"]["amount"] == "1800000"
    assert len(lines["Taxable salary"]["certificates"]) == 1


async def test_the_mcp_tool_counts_only_the_confirmed_certificate(
    client: AsyncClient, db: AsyncSession, two_certificates: User
) -> None:
    """Fails if the unconfirmed certificate's figures reach calculate_income_tax."""
    token = await create_token(db, two_certificates.id, "MCP client")

    async with Client(build_server(token, sessions_of(db), FakeEmbedder())) as mcp:
        result: Any = await mcp.call_tool("calculate_income_tax", {})

    assert not result.is_error, result.content
    tool = json.loads(result.content[0].text)
    assert tool["salary_tax"] == SALARY_TAX
    assert tool == (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()


async def test_the_guided_gate_shows_only_the_confirmed_certificate(
    client: AsyncClient, two_certificates: User
) -> None:
    """Fails if the figures the user approves include the unconfirmed certificate."""
    assert two_certificates

    run = (await client.post("/api/workflow/start", json={})).json()

    assert run["step"] == "gate"
    assert run["gate"]["figures"]["taxable_salary"] == "1800000.00"
    assert run["gate"]["figures"]["tax_deducted"] == "75000.00"


async def test_no_guided_result_or_pdf_without_an_approval(
    client: AsyncClient, two_certificates: User
) -> None:
    """Fails if the guided result, or its PDF, is given out before the user approves."""
    assert two_certificates
    await client.post("/api/workflow/start", json={})

    for url in ("/api/workflow/result", "/api/workflow/result/pdf"):
        response = await client.get(url)
        assert response.status_code == 409, url
