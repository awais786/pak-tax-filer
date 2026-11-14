"""The simple tax calculator (feature 010; specs/010-income-tax-engine/research.md R1-R7).

A pure function, like 004's engine beside it: the same typed amounts always give the same
result. No database, network, clock or AI is imported here (a test and import-linter enforce
that, Principle I). Amounts are exact Decimals; only the final tax lines are rounded, to the
nearest rupee with 50 paisa or more going up (section 219), and the total is their sum.

The order (research R6): yearly amounts; property income after the repairs allowance; taxable
income (salary + property; dividends and bank profit are final taxes outside it, s.8(1)(a)); the
75% test picks the table; slab tax; surcharge; dividend and profit tax. Then the extras (R7): the
monthly view an employer deducts (s.149), the effective rate, the bonus impact, and the filer vs
non-filer deductions.

The legal readings are provisional until a tax practitioner reviews the app (spec, FR-012).
"""

from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.tax import breakdown as words
from app.tax.engine import Step, band_for, rupees
from app.tax.rates.model import Band, Rule, Source, TaxYearRates

Table = Literal["salaried", "non_salaried"]
ZERO = Decimal(0)
HUNDRED = Decimal(100)
MONTHS = Decimal(12)
# What the calculator doesn't cover, shown with every result (FR-010; data-model.md).
NOT_COVERED = (
    "Tax already deducted, and whether you owe more or get a refund",
    "Freelance, business, capital gains and other incomes",
    "Zakat, donations, pension and other deductions or tax credits",
    "Property deductions other than the one-fifth repairs allowance (s.15A)",
    "Dividends taxed at other rates (power producers, mutual funds, REIT SPVs, "
    "companies that pay no tax)",
    "Bank profit above Rs 5 million",
    "Exempt allowances in your salary",
    "Tax year 2027",
)


@dataclass(frozen=True)
class CalculatorInputs:  # pylint: disable=too-many-instance-attributes  # one field per input
    """What the user typed, plus the tax year and ATL status from their profile."""

    tax_year: str
    atl: bool
    salary_monthly: Decimal = ZERO
    bonus: Decimal = ZERO
    rent_monthly: Decimal = ZERO
    dividends: Decimal = ZERO
    bank_profit: Decimal = ZERO


@dataclass(frozen=True)
class IncomeLine:
    """One income above zero: its yearly amount, the part that is taxed, and how."""

    source: Literal["salary", "bonus", "rent", "dividends", "bank_profit"]
    yearly_amount: Decimal
    taxable_amount: Decimal
    treatment: Literal["slab", "final", "separate"]


@dataclass(frozen=True)
class MonthlyView:
    """What an employer deducts each month on the salary alone, and what is left (s.149)."""

    salary_tax: Decimal
    take_home: Decimal


@dataclass(frozen=True)
class FilerLine:  # pylint: disable=too-many-instance-attributes  # one field per figure
    """Tax deducted at source on dividends or bank profit at each ATL status (not the tax)."""

    source: Literal["dividends", "bank_profit"]
    your_rate: Decimal
    other_rate: Decimal
    your_deduction: Decimal
    other_deduction: Decimal
    difference: Decimal


@dataclass(frozen=True)
class CalculatorResult:  # pylint: disable=too-many-instance-attributes  # one field per figure
    """The calculator's figures, or why it refused (then every figure is None)."""

    tax_year: str
    blocked_reason: Literal["no_income", "profit_over_limit"] | None = None
    incomes: tuple[IncomeLine, ...] = ()
    taxable_income: Decimal | None = None
    # Salary income as a percentage of taxable income, 2 places; None without taxable income.
    salary_share: Decimal | None = None
    table: Table | None = None
    slab_tax: Decimal | None = None
    surcharge: Decimal | None = None
    dividend_tax: Decimal | None = None
    profit_tax: Decimal | None = None
    total_tax: Decimal | None = None
    # Total tax as a percentage of total yearly gross income, 1 place.
    effective_rate: Decimal | None = None
    monthly: MonthlyView | None = None
    bonus_impact: Decimal | None = None
    filer_comparison: tuple[FilerLine, ...] = ()
    steps: tuple[Step, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _Figures:  # pylint: disable=too-many-instance-attributes  # the working, kept together
    """The working for one set of inputs, exact and rounded."""

    salary_income: Decimal
    rent: Decimal
    allowance: Decimal
    taxable: Decimal
    table: Table | None
    band: Band | None
    slab_exact: Decimal
    surcharge_rule: Rule | None
    surcharge_exact: Decimal
    dividend_exact: Decimal
    profit_exact: Decimal

    @property
    def total(self) -> Decimal:
        """The sum of the rounded lines (research R6, step 8)."""
        return (
            rupees(self.slab_exact)
            + rupees(self.surcharge_exact)
            + rupees(self.dividend_exact)
            + rupees(self.profit_exact)
        )


# The citation for figures worked out from the lines above, which no rule of the Ordinance sets
# (the effective rate, the bonus impact; backend review L4).
DERIVED = "Worked out from the lines above (not a separate rule)"


def percent_text(rate: Decimal) -> str:
    """'15' for 0.15, '7.5' for 0.075: a rate as a plain percentage."""
    return f"{(rate * HUNDRED).normalize():f}"


def where(source: Source, rates: TaxYearRates) -> str:
    """A step's citation: the rule's location and the date it applies from (Principle II)."""
    return f"{words.where(source)}; effective {rates.effective_from.isoformat()}"


def calculate_simple(inputs: CalculatorInputs, rates: TaxYearRates) -> CalculatorResult:
    """The tax on the typed incomes for one tax year, each line explained; or the reason the
    calculator can't answer, with no figures at all."""
    reason = _blocked_reason(inputs, rates)
    if reason is not None:
        return CalculatorResult(tax_year=inputs.tax_year, blocked_reason=reason)

    work = _figures(inputs, rates)
    total = work.total
    gross = work.salary_income + work.rent + inputs.dividends + inputs.bank_profit
    effective = (total / gross * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    share = None
    if work.taxable > 0:
        share = (work.salary_income / work.taxable * HUNDRED).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    bonus_impact = None
    if inputs.salary_monthly > 0 and inputs.bonus > 0:
        bonus_impact = total - _figures(replace(inputs, bonus=ZERO), rates).total
    monthly = _monthly(inputs, rates)
    filers = _filer_lines(inputs, rates)

    return CalculatorResult(
        tax_year=inputs.tax_year,
        incomes=_incomes(inputs, work),
        taxable_income=work.taxable,
        salary_share=share,
        table=work.table,
        slab_tax=rupees(work.slab_exact),
        surcharge=rupees(work.surcharge_exact),
        dividend_tax=rupees(work.dividend_exact),
        profit_tax=rupees(work.profit_exact),
        total_tax=total,
        effective_rate=effective,
        monthly=monthly,
        bonus_impact=bonus_impact,
        filer_comparison=filers,
        steps=tuple(_steps(inputs, rates, work, share, (effective, gross, bonus_impact, monthly))),
    )


def _blocked_reason(
    inputs: CalculatorInputs, rates: TaxYearRates
) -> Literal["no_income", "profit_over_limit"] | None:
    """Why the calculator must refuse, if it must (contracts/calculator-api.md)."""
    amounts = (
        inputs.salary_monthly,
        inputs.bonus,
        inputs.rent_monthly,
        inputs.dividends,
        inputs.bank_profit,
    )
    if not any(amount > 0 for amount in amounts):
        return "no_income"
    if inputs.bank_profit > rates.profit_limit.value:
        return "profit_over_limit"  # s.7B(3)(b): s.7B stops applying; not covered (FR-009)
    return None


def _figures(inputs: CalculatorInputs, rates: TaxYearRates) -> _Figures:
    """The calculation itself (research R6, steps 1-7), exact."""
    salary_income = inputs.salary_monthly * MONTHS + inputs.bonus
    rent = inputs.rent_monthly * MONTHS
    allowance = rent * rates.repairs_allowance.value
    taxable = salary_income + rent - allowance

    table: Table | None = None
    band = None
    slab = ZERO
    if taxable > 0:
        salaried = salary_income > rates.salary_share_threshold.value * taxable
        table = "salaried" if salaried else "non_salaried"
        band = band_for(rates.salary_bands if salaried else rates.non_salaried_bands, taxable)
        slab = band.fixed + band.rate * (taxable - band.lower)

    surcharge_rule = None
    surcharge = ZERO
    if taxable > rates.surcharge_threshold.value:
        # s.4AB: 9% for an individual with income under the head Salary, 10% otherwise.
        surcharge_rule = rates.surcharge_rate if salary_income > 0 else rates.surcharge_rate_other
        surcharge = surcharge_rule.value * slab

    return _Figures(
        salary_income=salary_income,
        rent=rent,
        allowance=allowance,
        taxable=taxable,
        table=table,
        band=band,
        slab_exact=slab,
        surcharge_rule=surcharge_rule,
        surcharge_exact=surcharge,
        dividend_exact=inputs.dividends * rates.dividend_rate.value,
        profit_exact=inputs.bank_profit * rates.profit_rate.value,
    )


def _incomes(inputs: CalculatorInputs, work: _Figures) -> tuple[IncomeLine, ...]:
    """One line per income above zero."""
    salary = inputs.salary_monthly * MONTHS
    lines = [
        IncomeLine("salary", salary, salary, "slab"),
        IncomeLine("bonus", inputs.bonus, inputs.bonus, "slab"),
        IncomeLine("rent", work.rent, work.rent - work.allowance, "slab"),
        IncomeLine("dividends", inputs.dividends, inputs.dividends, "final"),
        IncomeLine("bank_profit", inputs.bank_profit, inputs.bank_profit, "separate"),
    ]
    return tuple(line for line in lines if line.yearly_amount > 0)


def _monthly(inputs: CalculatorInputs, rates: TaxYearRates) -> MonthlyView | None:
    """s.149: the salaried table (+9% above Rs 10m) on the monthly salary x 12 alone, / 12."""
    if inputs.salary_monthly <= 0:
        return None
    yearly = inputs.salary_monthly * MONTHS
    band = band_for(rates.salary_bands, yearly)
    tax = band.fixed + band.rate * (yearly - band.lower)
    if yearly > rates.surcharge_threshold.value:
        tax += rates.surcharge_rate.value * tax
    per_month = rupees(tax / MONTHS)
    return MonthlyView(salary_tax=per_month, take_home=inputs.salary_monthly - per_month)


def _filer_lines(inputs: CalculatorInputs, rates: TaxYearRates) -> tuple[FilerLine, ...]:
    """Deductions at source on dividends and bank profit, at each ATL status (Tenth Schedule
    rule 1 raises the rate by non_atl_increase for someone not on the list)."""
    lines = []
    deductions: tuple[tuple[Literal["dividends", "bank_profit"], Decimal, Decimal], ...] = (
        ("dividends", inputs.dividends, rates.dividend_deduction_rate.value),
        ("bank_profit", inputs.bank_profit, rates.profit_deduction_rate.value),
    )
    for source, amount, base in deductions:
        if amount <= 0:
            continue
        filer = base
        non_filer = base * (1 + rates.non_atl_increase.value)
        yours, other = (filer, non_filer) if inputs.atl else (non_filer, filer)
        your_deduction = rupees(amount * yours)
        other_deduction = rupees(amount * other)
        lines.append(
            FilerLine(
                source=source,
                your_rate=yours,
                other_rate=other,
                your_deduction=your_deduction,
                other_deduction=other_deduction,
                difference=abs(other_deduction - your_deduction),
            )
        )
    return tuple(lines)


def _steps(
    inputs: CalculatorInputs,
    rates: TaxYearRates,
    work: _Figures,
    share: Decimal | None,
    extras: tuple[Decimal, Decimal, Decimal | None, MonthlyView | None],
) -> list[Step]:
    """The breakdown, in the order of the calculation, each line citing its rule."""
    return [
        *_income_steps(inputs, rates, work, share),
        *_tax_steps(inputs, rates, work),
        *_extra_steps(inputs, rates, work, extras),
    ]


def _income_steps(
    inputs: CalculatorInputs, rates: TaxYearRates, work: _Figures, share: Decimal | None
) -> list[Step]:
    """Salary income, property income, taxable income and the table."""
    steps = []
    if work.salary_income > 0:
        parts = []
        if inputs.salary_monthly > 0:
            parts.append(f"{words.money(inputs.salary_monthly)} a month x 12")
        if inputs.bonus > 0:
            parts.append(f"bonus {words.money(inputs.bonus)} (a bonus is salary)")
        steps.append(
            Step(
                f"Salary income: {' + '.join(parts)} = {words.money(work.salary_income)}",
                where(rates.bonus_is_salary, rates),
                work.salary_income,
            )
        )
    if work.rent > 0:
        steps.append(
            Step(
                f"Property income: rent {words.money(work.rent)} less the repairs allowance of "
                f"one-fifth, {words.money(work.allowance)} = "
                f"{words.money(work.rent - work.allowance)}",
                where(rates.repairs_allowance.source, rates),
                work.rent - work.allowance,
            )
        )
    if work.taxable > 0 and work.band is not None and share is not None:
        threshold = rates.salary_share_threshold
        shown = f"{share}%"
        exceeds = "exceeds" if work.table == "salaried" else "does not exceed"
        if work.table == "salaried" and share == threshold.value * HUNDRED:
            shown, exceeds = "just over 75%", "so it exceeds"
        name = "salaried" if work.table == "salaried" else "non-salaried"
        steps.append(
            Step(
                f"Taxable income: {words.money(work.salary_income)} + "
                f"{words.money(work.rent - work.allowance)} = {words.money(work.taxable)} "
                "(dividends and bank profit are taxed on their own, outside it). Salary is "
                f"{shown} of it, which {exceeds} {words.percent(threshold.value)}: the {name} "
                "table applies",
                # The 75% test is clause (2)'s rule, whichever table it picks; the slab row is
                # cited by the next step.
                where(threshold.source, rates),
                work.taxable,
            )
        )
    return steps


def _tax_steps(inputs: CalculatorInputs, rates: TaxYearRates, work: _Figures) -> list[Step]:
    """Slab tax, surcharge, dividend tax, profit tax and the total."""
    steps = []
    band = work.band
    if band is not None:
        slab = rupees(work.slab_exact)
        text = words.salary_tax(
            band, work.taxable, work.slab_exact, slab, lead="Tax on taxable income"
        )
        steps.append(Step(text, where(band.source, rates), slab))
    limit = rates.surcharge_threshold
    if work.surcharge_rule is not None:
        surcharge = rupees(work.surcharge_exact)
        steps.append(
            Step(
                f"Surcharge: taxable income {words.money(work.taxable)} exceeds "
                f"{words.money(limit.value)}: {words.percent(work.surcharge_rule.value)} of "
                f"{words.money(work.slab_exact)} {words.equals(work.surcharge_exact, surcharge)}",
                where(work.surcharge_rule.source, rates),
                surcharge,
            )
        )
    if inputs.dividends > 0:
        tax = rupees(work.dividend_exact)
        steps.append(
            Step(
                f"Tax on dividends: {words.percent(rates.dividend_rate.value)} of "
                f"{words.money(inputs.dividends)} {words.equals(work.dividend_exact, tax)} "
                "(a final tax)",
                where(rates.dividend_rate.source, rates),
                tax,
            )
        )
    if inputs.bank_profit > 0:
        tax = rupees(work.profit_exact)
        steps.append(
            Step(
                f"Tax on bank profit: {words.percent(rates.profit_rate.value)} of "
                f"{words.money(inputs.bank_profit)} {words.equals(work.profit_exact, tax)} "
                "(taxed separately)",
                where(rates.profit_rate.source, rates),
                tax,
            )
        )
    steps.append(
        Step(
            "Total tax: the sum of the lines above, each rounded to the rupee",
            where(rates.rounding, rates),
            work.total,
        )
    )
    return steps


def _extra_steps(
    inputs: CalculatorInputs,
    rates: TaxYearRates,
    work: _Figures,
    extras: tuple[Decimal, Decimal, Decimal | None, MonthlyView | None],
) -> list[Step]:
    """The effective rate, the monthly view and the bonus impact (research R7)."""
    effective, gross, bonus_impact, monthly = extras
    steps = [
        Step(
            f"Effective rate: total tax {words.money(work.total)} / total income "
            f"{words.money(gross)} = {effective}%",
            DERIVED,
            effective,
        )
    ]
    if monthly is not None:
        steps.append(
            Step(
                f"Each month your employer deducts about {words.money(monthly.salary_tax)} on "
                f"the salary alone, leaving {words.money(monthly.take_home)}",
                where(rates.salary_withholding, rates),
                monthly.salary_tax,
            )
        )
    if bonus_impact is not None:
        steps.append(Step(_bonus_words(inputs.bonus, bonus_impact), DERIVED, bonus_impact))
    return steps


def _bonus_words(bonus: Decimal, impact: Decimal) -> str:
    """What the bonus does to the total. It can lower it: a bonus that lifts salary over 75% of
    taxable income moves everything to the salaried table, which is never higher (backend review
    M1; a cliff in the Ordinance's two tables, for the tax practitioner to confirm)."""
    if impact > 0:
        effect = f"adds {words.money(impact)} to the total tax"
    elif impact < 0:
        effect = (
            f"lowers the total tax by {words.money(-impact)}, because it lifts salary over 75% "
            "and the salaried table applies"
        )
    else:
        effect = "doesn't change the total tax"
    return f"Your bonus of {words.money(bonus)} {effect} (the tax with it minus the tax without it)"
