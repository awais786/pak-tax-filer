"""The PDF banner's validation-status lines (feature 008, task T003; research R7).

Built from what 003-007 already provide (confirmed certificates and 003's rules, 005's
provisional lines, 007's approval date); nothing new is calculated (Principle I). Every banner
starts with the same practitioner label the result screens show, so one string is checked.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from app.documents.extraction.rules import check_rules
from app.documents.models import DocType
from app.documents.service import ConfirmedDocument
from app.wealth.schemas import AutoFilledLine

LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
DEMO = "Demo data only."
# Pakistan Standard Time (no daylight saving): dates read as the user's own day, not UTC's.
PAKISTAN = timezone(timedelta(hours=5), "PKT")
NO_WARNINGS = "No warnings"
_TYPE_NAMES = {
    DocType.SALARY_CERTIFICATE: "Salary certificate",
    DocType.BANK_PROFIT_CERTIFICATE: "Bank certificate",
}


def banner_head(tax_year: str, generated: date) -> list[str]:
    """The lines every PDF page starts with."""
    return [LABEL, DEMO, f"Tax year {tax_year} · generated {generated:%d %b %Y}"]


def tax_status(documents: Sequence[ConfirmedDocument], profile_tax_year: str) -> list[str]:
    """Where the tax figures come from, then 003's rule warnings on those certificates."""
    warnings = [
        f"{_name(document)}: {reason}"
        for document in documents
        # One line per reason: 003 gives a broken rule's reason to both fields involved.
        for reason in dict.fromkeys(
            check_rules(document.doc_type, document.values, profile_tax_year).values()
        )
    ]
    return ["All figures are from your confirmed certificates", *(warnings or [NO_WARNINGS])]


def workflow_status(
    documents: Sequence[ConfirmedDocument], profile_tax_year: str, approved_at: datetime
) -> list[str]:
    """As the tax status, plus when the user approved the guided run's inputs."""
    approved = approved_at.astimezone(PAKISTAN)
    return [*tax_status(documents, profile_tax_year), f"Approved by you on {approved:%d %b %Y}"]


def wealth_status(auto_filled: Sequence[AutoFilledLine]) -> list[str]:
    """Where the wealth figures come from, then 005's provisional lines in use."""
    provisional = [
        line.label for line in auto_filled if line.provisional and _non_zero(line.amount)
    ]
    notes = (
        [f"Provisional (may change): {', '.join(provisional)}"] if provisional else [NO_WARNINGS]
    )
    return [
        "Salary figures are from your confirmed certificates; other rows were entered by you",
        *notes,
    ]


def _name(document: ConfirmedDocument) -> str:
    name = _TYPE_NAMES.get(document.doc_type, "Certificate")
    if document.uploaded_at is None:
        return name
    return f"{name} uploaded {document.uploaded_at.astimezone(PAKISTAN):%d %b %Y}"


def _non_zero(amount: str) -> bool:
    return amount.strip().lstrip("-").strip("0.") != ""
