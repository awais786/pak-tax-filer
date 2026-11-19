# Contract: Tax API

`GET /api/tax/{tax_year}`. Requires `current_user`. ATL status is read from the user's taxpayer
profile (feature 002's `get_profile`). Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md): money as decimal
strings (plain digits, an optional leading `-`, never an exponent).

Every response has **all** the fields below; a field that doesn't apply is `null` (or `[]` for
`steps`).

| Field | Calculated | Blocked |
|---|---|---|
| `tax_year` | the year | the year |
| `blocked_reason`, `message` | `null` | the reason and what to do |
| `salary_tax`, `surcharge`, `profit_tax` | amounts | `null` |
| `salary_balance` | positive payable, negative over-deducted | `null` |
| `profit_balance` | positive payable, negative over-withheld | `null` |
| `non_atl_extra_withheld` | non-ATL only, else `null` | `null` |
| `salary_credit` | tax deducted by employers, rounded (s.219) | `null` |
| `profit_credit` | tax withheld by banks as counted against the profit tax (non-ATL: up to the profit tax), rounded | `null` |
| `steps` | the breakdown, in order | `[]` |
| `summary` | plain sentences written by code from the amounts above (added 2026-11-16) | `null` |
| `label` | always | always |

Credits (tax deducted by employers, tax withheld by banks) appear in the salary-side and
profit-side steps of the breakdown (FR-005), and, since 2026-11-11, also as `salary_credit` and
`profit_credit`, so a page can show "tax + surcharge − credit = balance" without doing sums
(feature 001, User Story 6; the frontend never calculates). Each is rounded on its own, so on
rare occasions the shown lines can differ from the balance by Rs 1; the balance is the figure
that counts. When they do, `summary` drops its "so" and says each amount is rounded on its own
(added 2026-11-16; a live certificate, tax Rs 167,393.50, hit it).

## 200: calculated

```json
{
  "tax_year": "2025-26", "blocked_reason": null, "message": null,
  "salary_tax": "72000", "surcharge": "0", "profit_tax": "10000",
  "salary_balance": "-3000", "profit_balance": "0", "non_atl_extra_withheld": null,
  "salary_credit": "75000", "profit_credit": "10000",
  "steps": [
    { "description": "Salary tax: Rs 1,800,000 falls in the Rs 1,200,001 to Rs 2,200,000 band: Rs 6,000 + 11% of Rs 600,000",
      "rule_location": "Income Tax Ordinance 2001 (amended up to 31.07.2025), First Schedule, Part I, Division I, clause (2), row 3",
      "result": "72000" }
  ],
  "summary": "Your salary tax for 2025-26 is Rs 72,000. Tax deducted from your salary was Rs 75,000, so Rs 3,000 was deducted too much. Tax on your bank profit is Rs 10,000; after Rs 10,000 withheld by banks, nothing more is payable on your bank profit.",
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

## 200: blocked

```json
{
  "tax_year": "2025-26", "blocked_reason": "needs_atl_answer",
  "message": "Set your ATL status in your profile.",
  "salary_tax": null, "surcharge": null, "profit_tax": null,
  "salary_balance": null, "profit_balance": null, "non_atl_extra_withheld": null,
  "salary_credit": null, "profit_credit": null,
  "steps": [], "summary": null,
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

`blocked_reason` values: `needs_atl_answer`, `no_confirmed_salary_certificate`,
`profit_over_limit`. (`salary_share_ambiguous` and `surcharge_ambiguous` were removed on 2026-11-17:
bank profit under s.7B is a final tax outside taxable income, s.8(1)(a), so it changes neither the
75% test nor the Rs 10 million surcharge limit, which is checked on salary alone.)

## GET /api/tax/{tax_year}/summary (removed 2026-11-16)

Removed with the AI summary it served (the lead: no AI where no reasoning is needed): the
breakdown explains every figure. The route now answers `404`.

## Errors

`404` unknown tax year; `401` not logged in.
