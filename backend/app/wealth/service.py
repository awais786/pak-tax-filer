"""Reading, saving and reconciling a wealth statement (feature 005, tasks T009, T022; research
R5, R7, R8).

Certificate figures come only from 003's confirmed_documents (Principle III), summed and rounded
by reconcile.build_inputs. The user's entries are stored; the result never is (FR-012). The
certificate-change notice compares the confirmed certificates now with those at the last save.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument, confirmed_documents
from app.tax.rates import rates_for
from app.tax.summary import Summariser
from app.wealth.models import WealthAsset, WealthExpense, WealthLiability, WealthStatement
from app.wealth.reconcile import (
    CertificateFigures,
    ReconciliationResult,
    UserEntries,
    WealthInputs,
    build_inputs,
    reconcile,
)
from app.wealth.schemas import (
    AssetOut,
    AutoFilledLine,
    LiabilityOut,
    ResultOut,
    StatementIn,
    StatementOut,
    StepOut,
    WealthOut,
)
from app.wealth.summary import verified_wealth_summary

# On every result (constitution Principle IV, FR-014); the same words as the tax page.
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."
_TYPE_NAMES = {
    DocType.SALARY_CERTIFICATE: "Salary certificate",
    DocType.BANK_PROFIT_CERTIFICATE: "Bank profit certificate",
}


@dataclass(frozen=True)
class Certificates:
    """The user's confirmed certificates for the year, as the reconciliation needs them."""

    salary: list[CertificateFigures]
    bank: list[CertificateFigures]
    ids: list[uuid.UUID]


def _name(document: ConfirmedDocument) -> str:
    """How a certificate is named on the page: original file names aren't stored (003 R4)."""
    when = f" uploaded {document.uploaded_at:%Y-%m-%d %H:%M:%S} UTC" if document.uploaded_at else ""
    return _TYPE_NAMES.get(document.doc_type, "Certificate") + when


def _amount(document: ConfirmedDocument, name: FieldName) -> Decimal:
    value = document.values.get(name)
    return value if isinstance(value, Decimal) else Decimal(0)


async def certificates(db: AsyncSession, user_id: uuid.UUID, tax_year: str) -> Certificates:
    """The confirmed certificates only (Principle III), with their figures unrounded."""
    documents = await confirmed_documents(db, user_id, tax_year)
    salary = [
        CertificateFigures(
            name=_name(d),
            gross_salary=_amount(d, FieldName.GROSS_SALARY),
            taxable_salary=_amount(d, FieldName.TAXABLE_SALARY),
            tax_deducted=_amount(d, FieldName.TAX_DEDUCTED),
        )
        for d in documents
        if d.doc_type is DocType.SALARY_CERTIFICATE
    ]
    bank = [
        CertificateFigures(
            name=_name(d),
            profit_amount=_amount(d, FieldName.PROFIT_AMOUNT),
            tax_withheld=_amount(d, FieldName.TAX_WITHHELD),
        )
        for d in documents
        if d.doc_type is DocType.BANK_PROFIT_CERTIFICATE
    ]
    return Certificates(salary, bank, sorted(d.id for d in documents))


async def get_statement(
    db: AsyncSession, user_id: uuid.UUID, tax_year: str
) -> WealthStatement | None:
    """The user's own saved statement for the year, if any (FR-016)."""
    result = await db.scalars(
        select(WealthStatement).where(
            WealthStatement.user_id == user_id, WealthStatement.tax_year == tax_year
        )
    )
    return result.one_or_none()


async def save_statement(
    db: AsyncSession, user_id: uuid.UUID, tax_year: str, body: StatementIn
) -> None:
    """Replace the whole statement, rows included, and note the certificates used (R7, R8)."""
    # Saves sent together (double-click, two tabs) wait for each other, held until the
    # transaction ends, instead of both inserting or both replacing rows (backend review M2).
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"wealth:{user_id}:{tax_year}"},
    )
    # Queries first: a query auto-flushes, so a new row must be complete before any runs.
    certificate_ids = (await certificates(db, user_id, tax_year)).ids
    statement = await get_statement(db, user_id, tax_year)
    now = datetime.now(UTC)
    if statement is None:
        statement = WealthStatement(user_id=user_id, tax_year=tax_year, saved_at=now)
        db.add(statement)
    statement.previous_net_assets = body.previous_net_assets
    statement.other_exempt_income = body.other_exempt_income
    statement.foreign_remittance = body.foreign_remittance
    statement.inheritance = body.inheritance
    statement.gifts_received = body.gifts_received
    statement.family_contribution = body.family_contribution
    statement.gifts_given = body.gifts_given
    statement.assets = [
        WealthAsset(position=i, category=a.category, description=a.description, amount=a.amount)
        for i, a in enumerate(body.assets)
    ]
    statement.liabilities = [
        WealthLiability(
            position=i, description=row.description, creditor=row.creditor, amount=row.amount
        )
        for i, row in enumerate(body.liabilities)
    ]
    statement.expenses = [
        WealthExpense(category=category, amount=amount)
        for category, amount in body.expenses.items()
    ]
    statement.certificate_ids = certificate_ids
    statement.saved_at = now
    await db.flush()


def _entries(statement: WealthStatement | None) -> UserEntries:
    if statement is None:
        return UserEntries(previous_net_assets=None)
    return UserEntries(
        previous_net_assets=statement.previous_net_assets,
        assets=tuple(a.amount for a in statement.assets),
        liabilities=tuple(row.amount for row in statement.liabilities),
        other_exempt_income=statement.other_exempt_income,
        foreign_remittance=statement.foreign_remittance,
        inheritance=statement.inheritance,
        gifts_received=statement.gifts_received,
        family_contribution=statement.family_contribution,
        personal_expenses=tuple(e.amount for e in statement.expenses),
        gifts_given=statement.gifts_given,
    )


def _plain(amount: Decimal) -> str:
    """Plain digits ("1350000"): the driver reads whole-rupee columns back as e.g.
    Decimal("1.35E+6"), which str() would send in scientific notation."""
    return format(amount, "f")


def _text(amount: Decimal | None) -> str | None:
    return None if amount is None else _plain(amount)


def _statement_out(statement: WealthStatement | None) -> StatementOut:
    if statement is None:
        zero = "0"
        return StatementOut(
            previous_net_assets=None,
            assets=[],
            liabilities=[],
            other_exempt_income=zero,
            foreign_remittance=zero,
            inheritance=zero,
            gifts_received=zero,
            family_contribution=zero,
            gifts_given=zero,
            expenses={},
            saved_at=None,
        )
    return StatementOut(
        previous_net_assets=_text(statement.previous_net_assets),
        assets=[
            AssetOut(category=a.category, description=a.description, amount=_plain(a.amount))
            for a in statement.assets
        ],
        liabilities=[
            LiabilityOut(
                description=row.description, creditor=row.creditor, amount=_plain(row.amount)
            )
            for row in statement.liabilities
        ],
        other_exempt_income=_plain(statement.other_exempt_income),
        foreign_remittance=_plain(statement.foreign_remittance),
        inheritance=_plain(statement.inheritance),
        gifts_received=_plain(statement.gifts_received),
        family_contribution=_plain(statement.family_contribution),
        gifts_given=_plain(statement.gifts_given),
        expenses={e.category.value: _plain(e.amount) for e in statement.expenses},
        saved_at=statement.saved_at,
    )


def _auto_filled(found: Certificates, rounded: dict[str, Decimal]) -> list[AutoFilledLine]:
    """The certificate lines, read-only, each naming its certificates (FR-004)."""
    salary = [c.name for c in found.salary]
    bank = [c.name for c in found.bank]
    return [
        AutoFilledLine(
            line="7031",
            label="Taxable salary",
            amount=_plain(rounded["taxable"]),
            certificates=salary,
        ),
        AutoFilledLine(
            line="7032",
            label="Exempt part of salary (gross - taxable)",
            amount=_plain(rounded["gross"] - rounded["taxable"]),
            certificates=salary,
            provisional=True,
        ),
        AutoFilledLine(
            line="7033",
            label="Bank profit",
            amount=_plain(rounded["profit"]),
            certificates=bank,
            provisional=True,
        ),
        AutoFilledLine(
            line=None,
            label="Tax deducted and withheld at source (outflow)",
            amount=_plain(rounded["tax"]),
            certificates=salary + bank,
            provisional=True,
        ),
    ]


def _result_out(result: ReconciliationResult) -> ResultOut:
    return ResultOut(
        not_ready_reason=result.not_ready_reason,
        message=result.message,
        net_assets=_text(result.net_assets),
        increase=_text(result.increase),
        inflows=_text(result.inflows),
        outflows=_text(result.outflows),
        unreconciled=_text(result.unreconciled),
        direction=result.direction,
        where_to_look=list(result.where_to_look),
        steps=[
            StepOut(description=s.description, form_line=s.form_line, result=_plain(s.result))
            for s in result.steps
        ],
    )


async def _reconciled(
    db: AsyncSession, user_id: uuid.UUID, tax_year: str
) -> tuple[WealthStatement | None, Certificates, WealthInputs, ReconciliationResult]:
    statement = await get_statement(db, user_id, tax_year)
    found = await certificates(db, user_id, tax_year)
    inputs = build_inputs(_entries(statement), found.salary, found.bank, rates_for(tax_year))
    return statement, found, inputs, reconcile(inputs)


async def wealth_view(db: AsyncSession, user_id: uuid.UUID, tax_year: str) -> WealthOut:
    """The saved statement, the certificate lines and a freshly computed result (R8). Never
    waits for the AI: the summary has its own request (wealth_summary)."""
    statement, found, inputs, result = await _reconciled(db, user_id, tax_year)
    rounded = {
        "taxable": inputs.taxable_salary,
        "gross": inputs.gross_salary,
        "profit": inputs.bank_profit,
        "tax": inputs.tax_deducted + inputs.tax_withheld,
    }
    return WealthOut(
        tax_year=tax_year,
        statement=_statement_out(statement),
        auto_filled=_auto_filled(found, rounded),
        # R7: certificates added or deleted since the last save (never saved: nothing to warn).
        certificates_changed=statement is not None and statement.certificate_ids != found.ids,
        result=_result_out(result),
        label=LABEL,
    )


async def wealth_summary(
    db: AsyncSession, user_id: uuid.UUID, tax_year: str, summariser: Summariser
) -> str | None:
    """A short checked summary of the same result, or None (feature 001, US6)."""
    *_, result = await _reconciled(db, user_id, tax_year)
    return await verified_wealth_summary(result, tax_year, summariser)
