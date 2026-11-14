"""The shape of a tax year's rates (feature 004, task T005, specs/004-tax-engine/data-model.md).

Rates are data, one module per tax year, each value carrying the FBR document, location and
Finance Act it comes from (constitution Principle II). Every number is a Decimal built from a
string, never a float (Principle I). Adding a tax year means adding data, not changing the engine.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Source:
    """Where a rule comes from in FBR's own law text."""

    # e.g. "Income Tax Ordinance, 2001 (amended up to 31.07.2025)"
    document: str
    # e.g. "First Schedule, Part I, Division I, clause (2), row 3 (p. 492, PDF p. 511)"
    location: str
    # e.g. "Finance Act 2025"
    finance_act: str


@dataclass(frozen=True)
class Rule:
    """One rate or limit, with its source."""

    value: Decimal
    source: Source


@dataclass(frozen=True)
class Band:
    """A row of the salaried table: income over `lower` and not over `upper` (None: no limit)
    pays `fixed` plus `rate` times the amount over `lower`."""

    lower: Decimal
    upper: Decimal | None
    fixed: Decimal
    rate: Decimal
    source: Source


@dataclass(frozen=True)
class TaxYearRates:  # pylint: disable=too-many-instance-attributes  # one field per rule
    """Every rate the engine uses for one tax year."""

    tax_year: str
    salary_bands: tuple[Band, ...]
    # The salaried table applies where salary exceeds this share of taxable income.
    salary_share_threshold: Rule
    # The surcharge rate on salary tax, where taxable income exceeds the threshold.
    surcharge_rate: Rule
    surcharge_threshold: Rule
    # The tax on gross bank profit, and the profit above which it no longer applies.
    profit_rate: Rule
    profit_limit: Rule
    # Final amounts to the nearest rupee, 50 paisa or more up.
    rounding: Source
    # Feature 010 (the simple calculator, specs/010-income-tax-engine/research.md):
    # the date this year's rules apply from (constitution 1.3.0, Principle II).
    effective_from: date
    # The table for everyone who isn't salaried (salary not more than 75% of taxable income).
    non_salaried_bands: tuple[Band, ...]
    # The surcharge rate without income under the head Salary (surcharge_rate is the salaried 9%).
    surcharge_rate_other: Rule
    # The repairs allowance on rent, as a share of the rent.
    repairs_allowance: Rule
    # Tax on ordinary dividends, and the rates deducted at source on dividends and bank profit.
    dividend_rate: Rule
    dividend_deduction_rate: Rule
    profit_deduction_rate: Rule
    # How much deduction rates rise for someone not on the active taxpayers' list (1.00 = +100%).
    non_atl_increase: Rule
    # Rules with no number, cited by the calculator's steps: a bonus is salary, and how an
    # employer deducts tax from salary each month (backend review M3: sources live here only).
    bonus_is_salary: Source
    salary_withholding: Source
