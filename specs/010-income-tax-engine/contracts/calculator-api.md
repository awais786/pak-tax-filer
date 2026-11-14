# Contract: Tax calculator API

`POST /api/tax/calculator`. Requires `current_user`, a taxpayer profile (`require_profile`: `409`
without one) and a JSON body (`require_json`: `415` otherwise). Nothing is stored; the answer is
`200`. Tax year and ATL status come from the profile. Follows the
[API conventions](../../../docs/api-conventions.md): money as decimal strings.

## Request

All fields optional, default `"0"`; each a **string** of ASCII digits ≥ 0, at most 2 decimal places
and 13 digits before the point (else `422`, the field named, the value never echoed; a JSON number,
`"1e5"` or `"1_000"` is refused, as in feature 005).

```json
{ "salary_monthly": "250000", "bonus": "0", "rent_monthly": "140000",
  "dividends": "0", "bank_profit": "0" }
```

## 200: calculated

Every field is always present. In a refusal every figure is `null` (lists `[]`). Otherwise the
tax lines (`slab_tax`, `surcharge`, `dividend_tax`, `profit_tax`) are `"0"` when nothing is due on
them; `salary_share` and `table` are `null` without taxable income, `monthly` without a salary,
`bonus_impact` without both salary and bonus. `bonus_impact` can be **negative**: a bonus that
lifts salary over 75% moves everything to the salaried table, which is never higher (backend
review M1). `on_atl` is the profile's ATL status the comparison used. Step `result`s are plain
digits (`"1344000"`); steps worked out from the lines above (the effective rate, the bonus
impact) cite `"Worked out from the lines above (not a separate rule)"`.

```json
{
  "tax_year": "2025-26", "blocked_reason": null, "message": null,
  "incomes": [
    { "source": "salary", "yearly_amount": "3000000", "taxable_amount": "3000000", "treatment": "slab" },
    { "source": "rent", "yearly_amount": "1680000", "taxable_amount": "1344000", "treatment": "slab" }
  ],
  "taxable_income": "4344000",
  "salary_share": "69.06", "table": "non_salaried",
  "slab_tax": "1107600", "surcharge": "0", "dividend_tax": "0", "profit_tax": "0",
  "total_tax": "1107600", "effective_rate": "23.7",
  "monthly": { "salary_tax": "25000", "take_home": "225000" },
  "bonus_impact": null,
  "filer_comparison": [], "on_atl": true,
  "steps": [
    { "description": "Rent Rs 1,680,000 less the repairs allowance of one-fifth, Rs 336,000 = Rs 1,344,000",
      "rule_location": "Income Tax Ordinance 2001 (amended up to 31.07.2025), section 15A(1)(a) (p. 57, PDF p. 76); effective 2025-07-01",
      "result": "1344000" }
  ],
  "not_covered": ["Tax already deducted, and whether you owe or get a refund", "…"],
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

(The lead's example, research R1: the 75% test fails, so the non-salaried table applies.)

`filer_comparison` items: `{ "source": "dividends", "your_rate": "15", "other_rate": "30",
"your_deduction": "15000", "other_deduction": "30000", "difference": "15000" }`.

## 200: blocked

`blocked_reason` is `no_income` (every amount zero) or `profit_over_limit` (bank profit above
Rs 5 million, s.7B(3)(b)); `message` says what to do; every figure `null`, lists `[]`, `monthly`
`null`; `not_covered` and `label` still present.

## Errors

`401` not signed in; `404` no rates for the profile's tax year (not possible while profiles allow
only TY2026); `409` no taxpayer profile; `415` not JSON; `422` invalid amount.
