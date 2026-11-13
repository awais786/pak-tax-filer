"""The PDF banner's validation-status lines (feature 008, task T003; research R7, FR-002 to FR-004).

Pure functions over what 003-007 already provide; nothing new is calculated.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument
from app.reports.status import (
    DEMO,
    LABEL,
    banner_head,
    tax_status,
    wealth_status,
    workflow_status,
)
from app.wealth.schemas import AutoFilledLine

UPLOADED = datetime(2026, 11, 5, 10, tzinfo=UTC)


def salary(taxable: str, gross: str = "2000000") -> ConfirmedDocument:
    """A confirmed salary certificate."""
    return ConfirmedDocument(
        id=uuid.uuid4(),
        doc_type=DocType.SALARY_CERTIFICATE,
        values={
            FieldName.TAX_YEAR: "2025-26",
            FieldName.GROSS_SALARY: Decimal(gross),
            FieldName.TAXABLE_SALARY: Decimal(taxable),
            FieldName.TAX_DEDUCTED: Decimal("75000"),
        },
        uploaded_at=UPLOADED,
    )


def test_every_banner_starts_with_the_label_demo_line_year_and_date() -> None:
    """Fails if the label (the one string the guardrails check) or "Demo data only." is lost."""
    head = banner_head("2025-26", date(2026, 11, 12))

    assert head == [LABEL, DEMO, "Tax year 2025-26 · generated 12 Nov 2026"]
    assert LABEL == "Not yet reviewed by a tax practitioner. Not tax advice."


def test_the_tax_status_says_where_figures_come_from_and_no_warnings() -> None:
    """Fails if clean certificates show anything but the source line and "No warnings"."""
    assert tax_status([salary("1800000")], "2025-26") == [
        "All figures are from your confirmed certificates",
        "No warnings",
    ]


def test_the_tax_status_lists_003s_rule_warnings_naming_the_certificate() -> None:
    """Fails if a certificate breaking one of 003's rules isn't flagged in the PDF (FR-003)."""
    status = tax_status([salary("2500000")], "2025-26")

    assert status[0] == "All figures are from your confirmed certificates"
    assert status[1:] == [
        "Salary certificate uploaded 05 Nov 2026: Taxable salary is more than gross salary."
    ]


def test_a_guided_run_adds_its_approval_date() -> None:
    """Fails if a guided-filing PDF doesn't say when the user approved it."""
    approved = datetime(2026, 11, 12, 10, 5, tzinfo=UTC)

    status = workflow_status([salary("1800000")], "2025-26", approved)

    assert status[-1] == "Approved by you on 12 Nov 2026"
    assert status[:2] == ["All figures are from your confirmed certificates", "No warnings"]


def test_the_wealth_status_lists_provisional_lines_in_use() -> None:
    """Fails if 005's provisional lines (rules the lead may change) aren't flagged (FR-004)."""

    def line(label: str, amount: str, provisional: bool) -> AutoFilledLine:
        return AutoFilledLine(
            line=None, label=label, amount=amount, certificates=[], provisional=provisional
        )

    lines = [
        line("Taxable salary", "1800000", False),
        line("Exempt part of salary (gross - taxable)", "200000", True),
        line("Bank profit", "0", True),  # nothing on this line: no note
    ]

    assert wealth_status(lines) == [
        "Salary figures are from your confirmed certificates; other rows were entered by you",
        "Provisional (may change): Exempt part of salary (gross - taxable)",
    ]
    assert wealth_status(lines[:1]) == [
        "Salary figures are from your confirmed certificates; other rows were entered by you",
        "No warnings",
    ]


def test_dates_are_the_users_day_in_pakistan() -> None:
    """Fails if a late-evening approval (after 19:00 UTC, already the next day in Pakistan)
    shows the UTC date."""
    late = datetime(2026, 11, 12, 20, 30, tzinfo=UTC)  # 01:30 on 13 Nov in Pakistan

    status = workflow_status([salary("1800000")], "2025-26", late)

    assert status[-1] == "Approved by you on 13 Nov 2026"
