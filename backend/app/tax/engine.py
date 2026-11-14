"""The TY2026 tax calculation (feature 004, task T010; research R1, R3).

A pure function: the same inputs always give the same result (constitution Principle I). No
database, network, clock or AI is imported here; a test enforces that. All amounts are exact
Decimals; only the final amounts (salary tax, surcharge, profit tax and each balance) are rounded,
to the nearest rupee with 50 paisa or more going up (section 219).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.tax import breakdown as words
from app.tax.rates.model import Band, TaxYearRates


@dataclass(frozen=True)
class TaxInputs:  # pylint: disable=too-many-instance-attributes  # one field per input
    """What the calculation needs: confirmed certificates summed per type, and ATL status."""

    tax_year: str
    # From the taxpayer profile; None when the user has no profile yet.
    atl: bool | None
    taxable_salary: Decimal
    tax_deducted: Decimal
    gross_profit: Decimal
    tax_withheld: Decimal
    has_salary_certificate: bool


@dataclass(frozen=True)
class Step:
    """One line of the breakdown: what was done, the rule it follows, and its result."""

    description: str
    rule_location: str
    result: Decimal


@dataclass(frozen=True)
class TaxResult:  # pylint: disable=too-many-instance-attributes  # one field per figure
    """The calculation's figures, or why it was refused (then every figure is None)."""

    tax_year: str
    blocked_reason: str | None = None
    salary_tax: Decimal | None = None
    surcharge: Decimal | None = None
    profit_tax: Decimal | None = None
    # Positive: payable. Negative: over-deducted / over-withheld. Never added together (FR-005).
    salary_balance: Decimal | None = None
    profit_balance: Decimal | None = None
    # Non-ATL only: withholding above the profit tax, "to be confirmed", never a refund.
    non_atl_extra_withheld: Decimal | None = None
    # What was taken off each side: tax deducted by employers, and tax withheld by banks as
    # counted against the profit tax (non-ATL: up to the profit tax). Shown so a reader sees
    # tax - credit = balance without doing sums (feature 001, User Story 6).
    salary_credit: Decimal | None = None
    profit_credit: Decimal | None = None
    steps: tuple[Step, ...] = field(default_factory=tuple)


def rupees(amount: Decimal) -> Decimal:
    """Round to the nearest rupee, 50 paisa or more up (section 219; never banker's rounding)."""
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return rounded if rounded else Decimal(0)  # never "-0" (e.g. 40 paisa over-deducted)


def band_for(bands: tuple[Band, ...], income: Decimal) -> Band:
    """The row of a table for this income ("does not exceed" the upper limit). Used for both
    tables of First Schedule, Part I, Division I (feature 010, task T007)."""
    for band in bands:
        if band.upper is None or income <= band.upper:
            return band
    raise ValueError("The bands don't cover this income.")


def salary_band(rates: TaxYearRates, taxable_salary: Decimal) -> Band:
    """The row of the salaried table for this income ("does not exceed" the upper limit)."""
    return band_for(rates.salary_bands, taxable_salary)


def blocked_reason(inputs: TaxInputs, rates: TaxYearRates) -> str | None:
    """Why the calculation must be refused, if it must (research R4; checked in this order).

    The last three are provisional rules pending the lead's answers, each one place to change.
    """
    if inputs.atl is None:
        return "needs_atl_answer"
    if not inputs.has_salary_certificate:
        return "no_confirmed_salary_certificate"
    if inputs.gross_profit > rates.profit_limit.value:
        return "profit_over_limit"  # Provisional rule 1: s.7B stops applying; don't guess.
    salary = inputs.taxable_salary
    threshold = rates.salary_share_threshold.value
    with_profit = salary > threshold * (salary + inputs.gross_profit)
    without_profit = salary > threshold * salary
    # Provisional rule 3: calculate only when both readings say the salaried table applies.
    # (Both saying it doesn't means the case is outside this app's scope: same refusal.)
    if not (with_profit and without_profit):
        return "salary_share_ambiguous"
    limit = rates.surcharge_threshold.value
    if (salary + inputs.gross_profit > limit) != (salary > limit):
        return "surcharge_ambiguous"
    return None


def calculate(inputs: TaxInputs, rates: TaxYearRates) -> TaxResult:
    """Salary tax, surcharge, profit tax and the two balances, for one taxpayer and tax year,
    each step explained; or the reason it can't be calculated, with no figures at all."""
    reason = blocked_reason(inputs, rates)
    if reason is not None:
        return TaxResult(tax_year=inputs.tax_year, blocked_reason=reason)

    band = salary_band(rates, inputs.taxable_salary)
    row = rates.salary_bands.index(band)
    salary_tax = band.fixed + band.rate * (inputs.taxable_salary - band.lower)

    income = inputs.taxable_salary + inputs.gross_profit
    surcharge = Decimal(0)
    if income > rates.surcharge_threshold.value:
        surcharge = rates.surcharge_rate.value * salary_tax

    profit_tax = rates.profit_rate.value * inputs.gross_profit
    salary_balance = salary_tax + surcharge - inputs.tax_deducted

    extra: Decimal | None = None
    credited = inputs.tax_withheld
    if inputs.atl is False:
        # Provisional rule 2: only withholding up to the profit tax counts against it.
        credited = min(inputs.tax_withheld, profit_tax)
        extra = rupees(inputs.tax_withheld - credited)
    profit_balance = profit_tax - credited

    rounded = {
        "salary_tax": rupees(salary_tax),
        "surcharge": rupees(surcharge),
        "profit_tax": rupees(profit_tax),
        "salary_balance": rupees(salary_balance),
        "profit_balance": rupees(profit_balance),
        "salary_credit": rupees(inputs.tax_deducted),
        "profit_credit": rupees(credited),
    }
    steps = _steps(inputs, rates, row, (salary_tax, surcharge, profit_tax, salary_balance), rounded)
    steps.append(_profit_side(inputs, rates, profit_tax, credited, extra, profit_balance, rounded))
    return TaxResult(
        tax_year=inputs.tax_year,
        salary_tax=rounded["salary_tax"],
        surcharge=rounded["surcharge"],
        profit_tax=rounded["profit_tax"],
        salary_balance=rounded["salary_balance"],
        profit_balance=rounded["profit_balance"],
        non_atl_extra_withheld=extra,
        salary_credit=rounded["salary_credit"],
        profit_credit=rounded["profit_credit"],
        steps=tuple(steps),
    )


def _steps(
    inputs: TaxInputs,
    rates: TaxYearRates,
    row: int,
    exact: tuple[Decimal, Decimal, Decimal, Decimal],
    rounded: dict[str, Decimal],
) -> list[Step]:
    """The salary tax, surcharge, profit tax and salary-side steps."""
    salary_tax, surcharge, profit_tax, salary_balance = exact
    band = rates.salary_bands[row]
    income = inputs.taxable_salary + inputs.gross_profit
    limit = rates.surcharge_threshold
    if surcharge:
        surcharge_text = (
            f"Surcharge: taxable income {words.money(income)} exceeds {words.money(limit.value)}: "
            f"{words.percent(rates.surcharge_rate.value)} of the salary tax "
            f"{words.money(salary_tax)} {words.equals(surcharge, rounded['surcharge'])}"
        )
        surcharge_source = rates.surcharge_rate.source
    else:
        surcharge_text = (
            f"Surcharge: taxable income {words.money(income)} does not exceed "
            f"{words.money(limit.value)}, so none = Rs 0"
        )
        surcharge_source = limit.source
    return [
        Step(
            words.salary_tax(band, inputs.taxable_salary, salary_tax, rounded["salary_tax"]),
            words.where(band.source),
            rounded["salary_tax"],
        ),
        Step(surcharge_text, words.where(surcharge_source), rounded["surcharge"]),
        Step(
            f"Tax on bank profit: {words.percent(rates.profit_rate.value)} of gross profit "
            f"{words.money(inputs.gross_profit)} {words.equals(profit_tax, rounded['profit_tax'])}",
            words.where(rates.profit_rate.source),
            rounded["profit_tax"],
        ),
        Step(
            f"Salary side: salary tax {words.money(salary_tax)} + surcharge "
            f"{words.money(surcharge)} - tax deducted by employers "
            f"{words.money(inputs.tax_deducted)} "
            f"{words.equals(salary_balance, rounded['salary_balance'])}: "
            f"{words.balance_words(rounded['salary_balance'], 'over-deducted')}",
            words.where(rates.rounding),
            rounded["salary_balance"],
        ),
    ]


def _profit_side(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    inputs: TaxInputs,
    rates: TaxYearRates,
    profit_tax: Decimal,
    credited: Decimal,
    extra: Decimal | None,
    profit_balance: Decimal,
    rounded: dict[str, Decimal],
) -> Step:
    """The profit-side step; for a non-ATL user, extra withholding is never called a refund."""
    if extra is None:
        text = (
            f"Profit side: tax on bank profit {words.money(profit_tax)} - tax withheld by banks "
            f"{words.money(inputs.tax_withheld)}"
        )
    else:
        text = (
            f"Profit side: tax on bank profit {words.money(profit_tax)} - the withholding up to "
            f"that tax {words.money(credited)}"
        )
    text += (
        f" {words.equals(profit_balance, rounded['profit_balance'])}: "
        f"{words.balance_words(rounded['profit_balance'], 'over-withheld')}"
    )
    if extra:
        text += (
            f". The other {words.money(extra)} withheld is extra tax for someone not on the ATL; "
            "whether it can be reclaimed needs confirmation"
        )
    return Step(text, words.where(rates.profit_rate.source), rounded["profit_balance"])
