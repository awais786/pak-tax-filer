# Implementation Plan: Simple Income Tax Calculator

**Branch**: `010-income-tax-engine` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/010-income-tax-engine/spec.md`

## Summary

A side Tax calculator: a signed-in user with a profile types salary per month, bonus, rent per
month, dividends and bank profit, and sees the tax on each, the total, which table applies and
why, a monthly view, the effective rate, what the bonus adds, and a filer vs non-filer comparison,
every line with its FBR source. Nothing is stored. The research (research.md) settled the law from
the Ordinance as amended up to 31.07.2025: rent is slab income after a one-fifth repairs allowance
and counts toward the 75% test and the surcharge limit; dividends (15%) and bank profit (20%) are
final taxes outside taxable income. The calculation is a new pure module beside 004's engine,
reusing its rounding, steps and band lookup, with new TY2026 rules in the guarded rates folder.

## Technical Context

**Language/Version**: Python ≥ 3.13 (backend), TypeScript ~7.0 with React 19 (frontend)

**Primary Dependencies**: FastAPI, Pydantic; React, Vite. No new dependency.

**Storage**: none (inputs and results never stored; no migration)

**Testing**: pytest (worked examples from YAML, API tests with the `client` fixture), Vitest +
React Testing Library, import-linter, the contract check

**Target Platform**: the existing Docker Compose stack and the GCP deployment

**Project Type**: web application (backend + frontend)

**Performance Goals**: result shown within 1 second of pressing Calculate (pure arithmetic);
SC-003's "under 1 minute" is the user's whole task

**Constraints**: `Decimal` only; s.219 rounding on final amounts; inputs never logged or sent to
AI; rates only from FBR's text with source and effective date

**Scale/Scope**: one endpoint, one page, about eight new rules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Pure `Decimal` module; no AI anywhere in the feature (no summary); import-linter forbids it |
| II. Authoritative sources | PASS | Every rule from the Ordinance (31.07.2025) with printed and PDF page, Finance Act and effective date (R1-R8); guarded folder; no third-party figures |
| III. Human confirmation | PASS (n/a) | No extracted values: the user types every amount |
| IV. Honest output | PASS | Label on every result; not-covered list; refusals for bank profit over Rs 5m; filer comparison worded as deductions, not refunds |
| V. Synthetic data only | PASS | Nothing stored or logged; tests use made-up amounts |
| VI. Test-first | PASS | Worked examples signed "author signed" before each part's code; a test fails while any is unsigned |
| VII. Scope (1.3.0) | PASS | Within the amended scope; a subset of it (the lead's "Simple") |
| Stack / Secrets | PASS | No new components or keys |

**Post-design re-check:** PASS, except governance: the lead's review of this spec and plan is
pending and gates the merge (tasks T008a, T027). One cross-feature note, not a violation: 004's Tax page keeps its
provisional `salary_share_ambiguous` refusal although s.8(1)(a) answers it (research R5); raised
with the lead in the PR rather than changed here (FR-005).

## Project Structure

### Documentation (this feature)

```text
specs/010-income-tax-engine/
├── plan.md
├── research.md            # R1–R9: the law, with pages
├── data-model.md          # in-code structures and new rules (no tables)
├── quickstart.md
├── contracts/calculator-api.md, api.yaml
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/tax/
│   ├── calculator.py          # NEW: pure calculation (inputs → result with steps)
│   ├── calculator_schemas.py  # NEW: request/response models, strict amount strings
│   ├── breakdown.py           # salary_tax() takes a lead phrase (shared wording)
│   ├── engine.py              # band lookup generalised; calculate() unchanged
│   ├── router.py              # NEW route POST /api/tax/calculator
│   └── rates/model.py, ty2026.py   # GUARDED: new fields and TY2026 rules; 004's page numbers corrected (R8)
├── .importlinter              # calculator added to the no-AI source modules
└── tests/tax/
    ├── calculator_examples.yaml   # NEW: signed worked examples
    ├── test_calculator_examples.py, test_calculator_api.py   # NEW
    └── test_rates.py, test_sign_off.py, test_engine_imports.py  # extended
frontend/src/
├── api/calculator.ts (+ test)     # NEW
├── pages/CalculatorPage.tsx (+ test)   # NEW
└── App.tsx, nav                   # /calculator route and link
e2e/tests/                          # one calculator scenario
```

**Structure Decision**: the existing backend/frontend layout; the calculator is a sibling of 004's
engine in `app/tax/`, so there is one engine package and 004's `calculate` is untouched (SC-004).

## Build order (each step: worked examples signed first, then failing tests, then code)

1. Rates: new fields and TY2026 values with sources; consistency test for the non-salaried table;
   004 page-number correction (after Saifullah checks his copy, R8).
2. Salary + bonus (both tables, surcharge 9%) and rent (repairs allowance, 75% test).
3. Dividends and bank profit (final, outside taxable income; `profit_over_limit`).
4. Extras: monthly view, effective rate, bonus impact, filer comparison.
5. Endpoint and contract; then the page; then e2e.

## Complexity Tracking

No violations to justify.
