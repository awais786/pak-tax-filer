"""The calculator's request and response (feature 010, task T012;
specs/010-income-tax-engine/contracts/calculator-api.md).

Money travels as decimal strings, never JSON numbers (docs/api-conventions.md). Amounts are
checked here, as feature 005 checks its own: ASCII digits only, at least zero, at most 2 decimal
places and 13 digits before the point (backend review M4).
"""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from app.tax.calculator import NOT_COVERED, CalculatorInputs, CalculatorResult, percent_text

# ASCII digits only (\d would accept other scripts' digits): up to 13 before the point, 2 after.
_AMOUNT = re.compile(r"[0-9]{1,13}(\.[0-9]{1,2})?")


def _amount(value: object) -> Decimal:
    """A decimal string of rupees as an exact Decimal; anything else is refused (422)."""
    if not isinstance(value, str) or not _AMOUNT.fullmatch(value.strip()):
        raise ValueError(
            "must be rupees written as a string of digits, at most 13 before the point and 2 after"
        )
    return Decimal(value.strip())


Amount = Annotated[Decimal, BeforeValidator(_amount)]
ZERO = Decimal(0)

# Why a result was refused, and what to do (contract, "200: blocked"; FR-009).
BLOCKED_MESSAGES = {
    "no_income": "Enter at least one income above zero.",
    "profit_over_limit": (
        "Bank profit above Rs 5 million isn't covered: section 7B no longer applies to it, so "
        "this needs a tax practitioner."
    ),
}


class CalculatorIn(BaseModel):
    """What the user typed; every amount optional. Tax year and ATL status are not here: they
    come from the profile (FR-011), and any other field is ignored."""

    salary_monthly: Amount = ZERO
    bonus: Amount = ZERO
    rent_monthly: Amount = ZERO
    dividends: Amount = ZERO
    bank_profit: Amount = ZERO

    def inputs(self, tax_year: str, atl: bool) -> CalculatorInputs:
        """The calculator's inputs, with the profile's tax year and ATL status."""
        return CalculatorInputs(
            tax_year=tax_year,
            atl=atl,
            salary_monthly=self.salary_monthly,
            bonus=self.bonus,
            rent_monthly=self.rent_monthly,
            dividends=self.dividends,
            bank_profit=self.bank_profit,
        )


class IncomeOut(BaseModel):
    """One income above zero."""

    source: str
    yearly_amount: str
    taxable_amount: str
    treatment: str


class MonthlyOut(BaseModel):
    """What an employer deducts each month on the salary alone (s.149), and what is left."""

    salary_tax: str
    take_home: str


class FilerOut(BaseModel):
    """Deductions at source at each ATL status; the tax itself doesn't change."""

    source: str
    your_rate: str
    other_rate: str
    your_deduction: str
    other_deduction: str
    difference: str


class CalculatorStepOut(BaseModel):
    """One line of the breakdown (named apart from 004's StepOut, so OpenAPI keeps both)."""

    description: str
    rule_location: str
    result: str


class CalculatorOut(BaseModel):  # pylint: disable=too-many-instance-attributes  # the contract
    """The contract's calculated or blocked result: every field always present."""

    tax_year: str
    blocked_reason: str | None
    message: str | None
    incomes: list[IncomeOut]
    taxable_income: str | None
    salary_share: str | None
    table: str | None
    slab_tax: str | None
    surcharge: str | None
    dividend_tax: str | None
    profit_tax: str | None
    total_tax: str | None
    effective_rate: str | None
    monthly: MonthlyOut | None
    bonus_impact: str | None
    filer_comparison: list[FilerOut]
    # The profile's ATL status the comparison used, so a page needn't rely on its own copy.
    on_atl: bool
    steps: list[CalculatorStepOut]
    not_covered: list[str]
    label: str


def money(amount: Decimal | None) -> str | None:
    """'4344000' for 4344000.00; paisa only when there are some ('99500.50')."""
    if amount is None:
        return None
    if amount == amount.to_integral_value():
        return f"{amount.quantize(Decimal(1)):f}"
    return f"{amount.quantize(Decimal('0.01')):f}"


def number(value: Decimal | None) -> str | None:
    """A percentage as computed ('69.06', '23.7')."""
    return None if value is None else f"{value:f}"


def step_number(value: Decimal) -> str:
    """A step's result as plain digits: '1344000' for 1344000.00, '23.7', '96000.096'."""
    return f"{value.normalize():f}"


def calculator_out(result: CalculatorResult, label: str, on_atl: bool) -> CalculatorOut:
    """The API form of a result."""
    monthly = None
    if result.monthly is not None:
        monthly = MonthlyOut(
            salary_tax=money(result.monthly.salary_tax) or "0",
            take_home=money(result.monthly.take_home) or "0",
        )
    return CalculatorOut(
        tax_year=result.tax_year,
        blocked_reason=result.blocked_reason,
        message=BLOCKED_MESSAGES.get(result.blocked_reason or ""),
        incomes=[
            IncomeOut(
                source=line.source,
                yearly_amount=money(line.yearly_amount) or "0",
                taxable_amount=money(line.taxable_amount) or "0",
                treatment=line.treatment,
            )
            for line in result.incomes
        ],
        taxable_income=money(result.taxable_income),
        salary_share=number(result.salary_share),
        table=result.table,
        slab_tax=money(result.slab_tax),
        surcharge=money(result.surcharge),
        dividend_tax=money(result.dividend_tax),
        profit_tax=money(result.profit_tax),
        total_tax=money(result.total_tax),
        effective_rate=number(result.effective_rate),
        monthly=monthly,
        bonus_impact=money(result.bonus_impact),
        filer_comparison=[
            FilerOut(
                source=line.source,
                your_rate=percent_text(line.your_rate),
                other_rate=percent_text(line.other_rate),
                your_deduction=money(line.your_deduction) or "0",
                other_deduction=money(line.other_deduction) or "0",
                difference=money(line.difference) or "0",
            )
            for line in result.filer_comparison
        ],
        on_atl=on_atl,
        steps=[
            CalculatorStepOut(
                description=s.description,
                rule_location=s.rule_location,
                result=step_number(s.result),
            )
            for s in result.steps
        ],
        not_covered=list(NOT_COVERED),
        label=label,
    )
