# Simple income tax calculator: design

2026-11-13, cut down 2026-11-14. From the lead's task prompt ("Implement Pakistan Individual Income
Tax Calculation Engine"), his feedback after trying the app (2026-11-12: "an interface to get info
for other incomes: salary per month, rental, shares or other earnings"), and his scope answer on
2026-11-14: "cover some basic scenarios on the side: user can just pass info like salary,
dividend, bonus, rental and you will show him tax kind of info; behind the scene some basic
formulas". Asked whether to keep it basic rather than his earlier full prompt, he answered
"Simple". His prompt's tool names (OpenSpec, Django) are read as this project's own (Spec Kit,
FastAPI).

## Intent and the why

Today the app calculates tax only from confirmed certificates (salary and bank profit, feature
004). A person who wants a quick idea of their tax with a bonus, rent or dividends has no way to
get it. This feature adds a **side calculator**: the user types a few numbers and sees the tax on
each, the total and how it was worked out, using the same engine and FBR-sourced rates.

## Goals

1. A Tax calculator page: salary per month, bonus per year, rent per month, dividends per year,
   bank profit per year (all optional; at least one).
2. The result: tax on each income, total tax, which table applies (salaried or not) and why, the
   slab used, a line-by-line breakdown with each rule's source, and the practitioner label.
3. Extras the user chose (2026-11-14): a monthly view (salary tax per month and take-home pay),
   the effective rate, the extra tax a bonus causes, and a filer vs non-filer comparison for
   dividends and bank profit.
4. Each income under its legal treatment for TY2026 (e.g. bonus as salary; rent and dividends as
   the Ordinance sets them), with the 75% salary test applied as the law says.

## Non-goals

Saving the inputs; tax deducted, payable or refundable; other incomes (freelance, business,
capital gains, other sources); Zakat, donations, pension and other deductions or credits; tax on
bills and advance tax; TY2027; linking the calculator to guided filing, the PDF, the MCP tool or
the wealth statement; filing or IRIS. All may come later, if the lead asks.

## Anti-goals (a failure even if it works)

- Any figure from a third-party calculator (Principle II): every rate comes from FBR's Ordinance
  and Finance Acts.
- A rule guessed when the law is unclear: shown as "needs a tax practitioner", never assumed.
- A second engine that can disagree with the Tax page: the calculator uses 004's engine.
- An LLM touching any figure (Principle I).

## Constraints

- Constitution 1.3.0 (its Principle VII amendment allows this and more); Principles I, II, IV, V
  and VI apply unchanged: `Decimal`, sources, the label, synthetic data, worked examples signed
  off before code.
- Sources: the Income Tax Ordinance 2001 amended to 31.07.2025 (Finance Act 2025), as 004 used.
- The rates folder stays guarded (the hook asks before changes); every change cites its source.

## Approaches (A chosen)

| | Approach | Trade-off |
|---|---|---|
| **A** | **Extend 004's engine** with plain functions for rent and dividends and their TY2026 rules; the calculator page calls it with typed amounts | One engine; small; 004's tests stay |
| B | A separate calculator module | Two engines can disagree |
| C | The full engine of the lead's earlier prompt | Far more than "simple" |

## Decided

- **Page:** a new Tax calculator page beside the current Tax page, which is unchanged.
- **Inputs:** typed, never stored. Salary is the taxable salary per month (as on a payslip); the
  page converts monthly amounts to yearly; the engine works on yearly amounts.
- **ATL status and tax year** from the taxpayer profile, as the Tax page does (TY2026).
- **Unclear cases** refuse with "needs a tax practitioner".
- **Worked examples** signed off by Saifullah ("author signed") before each income's code; every
  result keeps the practitioner label.

## Legal questions the research must answer from the Ordinance (not assumed here)

- How an individual's rent is taxed in TY2026 (separately, or in the slabs) and whether it counts
  toward the 75% salary test and the §4AB surcharge limit. (The lead's example: Rs 250,000 a month
  salary and Rs 140,000 a month rent.)
- Dividend tax for an individual (rate, final or not, ATL and non-ATL), and whether dividends
  count toward the 75% test.
- That a bonus is salary under §12 and taxed with it.

## Left to the builder (Spec Kit plan)

The endpoint's shape (following `docs/api-conventions.md`), the page layout, the breakdown's
wording, and how the engine's functions are split.
