# Data model: Simple Income Tax Calculator (feature 010)

**No tables, no migration.** Inputs are never stored (FR-003); everything below is an in-code
structure in the pure module `app/tax/calculator.py` or the rates in `app/tax/rates/`.

## Rates: additions to `TaxYearRates` (`app/tax/rates/model.py`, guarded)

New fields, each a `Rule` or `Band` with its `Source` (document, location with printed and PDF
page, Finance Act), filled for TY2026 in `ty2026.py` from research R1-R8:

| Field | TY2026 value | Source (research) |
|---|---|---|
| `effective_from` (`date`) | 2025-07-01 | R8 |
| `non_salaried_bands` | the six rows of clause (1) | R2 |
| `surcharge_rate_other` | 0.10 (no salary income) | R3; existing `surcharge_rate` 0.09 stays for salary |
| `repairs_allowance` | 0.20 (one-fifth of rent) | R1, s.15A(1)(a) |
| `dividend_rate` | 0.15 | R4, Division III(b) |
| `dividend_deduction_rate` | 0.15 | R4, Part III Division I(b) |
| `profit_deduction_rate` | 0.20 | R5, Part III Division IA(a) |
| `non_atl_increase` | 1.00 (+100%) | R4-R5, Tenth Schedule rule 1 |

Validation (tests): the non-salaried bands are contiguous and each fixed amount equals the tax at
the top of the previous band (004's FR-009 check, extended); every rule has a non-empty source.

## `CalculatorInputs` (frozen dataclass)

| Field | Type | Rule |
|---|---|---|
| `tax_year` | `str` | from the profile, e.g. `"2025-26"` |
| `atl` | `bool` | from the profile (`on_atl`) |
| `salary_monthly` | `Decimal` | ≥ 0 |
| `bonus` | `Decimal` | ≥ 0, yearly |
| `rent_monthly` | `Decimal` | ≥ 0 |
| `dividends` | `Decimal` | ≥ 0, yearly |
| `bank_profit` | `Decimal` | ≥ 0, yearly |

All amounts: at most 2 decimal places and 13 digits before the point (checked at the API).

## `CalculatorResult` (frozen dataclass; never stored)

| Field | Type | Meaning |
|---|---|---|
| `tax_year` | `str` | |
| `blocked_reason` | `str \| None` | `no_income`, `profit_over_limit`; when set, every figure is `None` and `steps` empty |
| `incomes` | `tuple[IncomeLine, ...]` | one per income above zero |
| `taxable_income` | `Decimal \| None` | salary income + property income |
| `salary_share` | `Decimal \| None` | salary income ÷ taxable income, as a percentage to 2 places; `None` without taxable income |
| `table` | `"salaried" \| "non_salaried" \| None` | `None` when there is no taxable income |
| `slab_tax`, `surcharge`, `dividend_tax`, `profit_tax`, `total_tax` | `Decimal \| None` | rounded (s.219); total = sum of the four |
| `effective_rate` | `Decimal \| None` | percent, 1 decimal place |
| `monthly` | `MonthlyView \| None` | `None` without salary |
| `bonus_impact` | `Decimal \| None` | only with salary and bonus; can be negative (the 75% cliff) |
| `filer_comparison` | `tuple[FilerLine, ...]` | one per dividends / bank profit above zero |
| (API only) `on_atl` | `bool` | the profile's ATL status the comparison used |
| `steps` | `tuple[Step, ...]` | 004's `Step` (description, rule location, result) |

`IncomeLine`: `source` (`salary`, `bonus`, `rent`, `dividends`, `bank_profit`), `yearly_amount`,
`taxable_amount` (rent: after the repairs allowance; dividends and bank profit: the gross amount),
`treatment` (`slab`, `final`, `separate`).

`MonthlyView`: `salary_tax` (per month, rounded), `take_home` (monthly salary − that).

`FilerLine`: `source`, `your_rate`, `other_rate`, `your_deduction`, `other_deduction`,
`difference` (rounded); "your" follows the profile's ATL status.

## Not-covered list (fixed text, no amounts)

Tax already deducted and the payable or refundable balance; freelance, business, capital gains and
other incomes; Zakat, donations, pension and other deductions or credits; s.15A property deductions
other than the repairs allowance; dividends taxed at other rates (IPP, mutual funds, REIT SPVs,
companies paying no tax); bank profit above Rs 5 million; exempt allowances; TY2027.
