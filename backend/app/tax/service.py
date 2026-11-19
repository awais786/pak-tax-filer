"""Gathering the calculation's inputs (feature 004, task T011; research R5).

Only confirmed certificates (feature 003's confirmed_documents, Principle III) summed per type,
and the ATL status from the taxpayer profile (feature 002). Nothing is stored: every request
recalculates from what is confirmed now.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument, confirmed_documents
from app.profile.service import get_profile
from app.tax.engine import TaxInputs

# What the user is told when the calculation is refused (contracts/tax-api.md).
BLOCKED_MESSAGES = {
    "needs_atl_answer": "Set your ATL status in your profile.",
    "no_confirmed_salary_certificate": "Upload and confirm your salary certificate first.",
    "profit_over_limit": "Bank profit over Rs 5,000,000 isn't supported yet.",
}


def _amount(value: Decimal | str | None) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(0)


async def tax_inputs(db: AsyncSession, user: User, tax_year: str) -> TaxInputs:
    """The user's confirmed figures for the year, summed per certificate type, and ATL status."""
    documents = await confirmed_documents(db, user.id, tax_year)
    profile = await get_profile(db, user)
    return tax_inputs_from(documents, tax_year, None if profile is None else profile.on_atl)


def tax_inputs_from(
    documents: list[ConfirmedDocument], tax_year: str, atl: bool | None
) -> TaxInputs:
    """The engine's inputs from certificates already read: 007 checks its gate and calculates
    from one read, so nothing confirmed in between can slip into an approved result."""
    salary = [d for d in documents if d.doc_type is DocType.SALARY_CERTIFICATE]
    bank = [d for d in documents if d.doc_type is DocType.BANK_PROFIT_CERTIFICATE]

    def total(certificates: list[ConfirmedDocument], name: FieldName) -> Decimal:
        return sum((_amount(c.values.get(name)) for c in certificates), Decimal(0))

    return TaxInputs(
        tax_year=tax_year,
        atl=atl,
        taxable_salary=total(salary, FieldName.TAXABLE_SALARY),
        tax_deducted=total(salary, FieldName.TAX_DEDUCTED),
        gross_profit=total(bank, FieldName.PROFIT_AMOUNT),
        tax_withheld=total(bank, FieldName.TAX_WITHHELD),
        has_salary_certificate=bool(salary),
    )
