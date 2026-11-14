---

description: "Task list for feature 010: Simple Income Tax Calculator"
---

# Tasks: Simple Income Tax Calculator

**Input**: Design documents from `/specs/010-income-tax-engine/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–008 implemented.

**Tests**: written first, from hand-worked examples signed off by the author (FR-012,
Principle VI). **No calculator code (T009 onward) starts until T003 is complete.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US3)

---

## Phase 1: Setup

- [X] T001 (manual) *(Resolved 2026-11-14 without the manual check, Saifullah's call: the pages of the file pinned by SHA-256 in `app/rag/sources.yaml` are used, being reproducible; 004's citations corrected to "p. / PDF p." in T006; to be revised at practitioner review.)* Saifullah opens his copy of the Ordinance (amended up to 31.07.2025) and notes the page number his viewer shows for the salaried table (printed page 492); research R8 expects PDF page 511. The answer decides whether T006 corrects feature 004's page numbers

---

## Phase 2: Foundational (blocking; sign-off gate)

- [X] T002 Write `backend/tests/tax/calculator_examples.yaml` (same layout as `worked_examples.yaml`: `id`, `description`, `inputs` {`atl`, `salary_monthly`, `bonus`, `rent_monthly`, `dividends`, `bank_profit`}, `working` citing research R1–R7 with pages, `expected`, empty `signed_off_by` / `signed_off_date`). Cases: the lead's example (salary 250,000/month + rent 140,000/month → taxable 4,344,000, share 69.06%, non-salaried, slab tax 1,107,600, effective 23.7%, monthly 25,000 / take-home 225,000); salary only inside each salaried row and on each upper limit; rent only inside each non-salaried row and on each upper limit (rent × 12 × 4/5 landing on the limit); salary exactly 75% of taxable income (non-salaried: "exceeds"); salary just over 75%; taxable income exactly 10,000,000 and just over, with salary (9%) and without (10%); a bonus that moves salary to a higher row (bonus impact); a bonus that flips the table; dividends only (ATL and non-ATL: tax 15% both, deductions 15% vs 30%); bank profit 5,000,000 (allowed) and 5,000,001 (`profit_over_limit`); dividends + bank profit + salary near 75% (they don't count); monthly salary with paisa (× 12 exactly, rounding only at the end); a case giving exactly 50 paisa before rounding; all zero (`no_income`)
- [X] T003 (manual) *(Accepted provisionally 2026-11-14, Saifullah's call: worked from the Ordinance and cross-checked by script, not hand-checked; every example to be revised at tax practitioner review, recorded in the YAML and each `signed_off_by`.)* **Saifullah:** check every example in `calculator_examples.yaml` by hand against the Ordinance pages in research.md, correct any error, fill `signed_off_by` and `signed_off_date` ("author signed"); readings that need the lead go in the PR
- [X] T004 [P] Extend `backend/tests/tax/test_sign_off.py` to fail on any unsigned example in `calculator_examples.yaml` as well
- [X] T005 [P] Extend `backend/tests/tax/test_rates.py`: `non_salaried_bands` contiguous, last unbounded, each `fixed` = previous `fixed + rate × (upper − lower)`; every new rule has a non-empty `Source`; `effective_from` is 2025-07-01 for TY2026
- [X] T006 Add the fields in [data-model.md](data-model.md) to `TaxYearRates` in `backend/app/tax/rates/model.py` and their TY2026 values and sources to `backend/app/tax/rates/ty2026.py` (non-salaried rows 0 / 15% / 90,000 + 20% / 170,000 + 30% / 650,000 + 40% / 1,610,000 + 45%; surcharge 10% without salary; repairs allowance 0.20; dividend 0.15; deductions 0.15 and 0.20; non-ATL increase 1.00; `effective_from` 2025-07-01), each location with printed and PDF page; if T001 confirms, correct 004's page numbers to the same scheme. Guarded folder: approve the hook prompt deliberately and call it out in review. T005 passes; 004's tests unchanged
- [X] T007 Generalise the band lookup in `backend/app/tax/engine.py` to `band_for(bands, income)` (keep `salary_band` calling it); `calculate()` unchanged; all 004 tests pass
- [X] T008 [P] Add `app.tax.calculator` to `source_modules` in `backend/.importlinter` and to the forbidden-import test in `backend/tests/tax/test_engine_imports.py` (no database, network, clock, AI or `app.tax.summary`)
- [X] T008a (manual) *(Met 2026-11-14 by the lead's own direction: his verbal approval of the design and his "Simple" answer, which this spec and plan follow word for word; Saifullah's call not to wait for a separate review. The plan summary and the R1 finding go in the PR and the `[010]` issue, opened with it as #46 was.)* **Review before build** (constitution, Development Workflow): Saifullah sends the lead a short summary of the spec and plan (scope, the research's key rules, the lead's example worked out) and gets his OK before T009. Open the feature issue `[010] Adding simple income tax calculator module` in the same format as #46 (spec, plan, tasks, contract, validation plan, depends on, done when)

**Checkpoint**: examples signed (T003); rates stored with sources and self-checked; the lead's OK on the spec and plan (T008a).

---

## Phase 3: User Story 1 - Type my incomes, see my tax (Priority: P1) 🎯 MVP

**Goal**: salary, bonus and rent give the signed figures to the rupee, with the table and why, the monthly view, effective rate and bonus impact.

**Independent Test**: [quickstart.md](quickstart.md), by-hand step 1.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T009 [P] [US1] Write `backend/tests/tax/test_calculator_examples.py`: one test per example without dividends or bank profit, asserting `taxable_income`, `salary_share`, `table`, `slab_tax`, `surcharge`, `total_tax`, `effective_rate`, `monthly` and `bonus_impact` equal the signed figures exactly

### Implementation for User Story 1

- [X] T010 [US1] Create `backend/app/tax/calculator.py`: frozen `CalculatorInputs`, `CalculatorResult`, `IncomeLine`, `MonthlyView`, `Step` reuse; pure `calculate_simple(inputs, rates)` following research R6 steps 1–6 and 8 (yearly amounts, property income = rent − rent × repairs allowance, taxable income, table by "exceeds" 75%, `band_for` on that table, surcharge 9% with salary / 10% without above 10,000,000, s.219 `rupees` on each final line, total = sum of rounded lines), plus effective rate (R7, one place, half-up); one `Step` per line with its rule's source and effective date
- [X] T011 [US1] Add to `calculator.py` the monthly view (s.149: salaried table + 9% surcharge on salary × 12 alone, ÷ 12, rounded; take-home = monthly salary − it; `None` without salary) and bonus impact (total − total with bonus 0; only with salary and bonus); T009 passes
- [X] T012 [US1] Write `backend/tests/tax/test_calculator_api.py` (`401` signed out; `409` no profile; `415` not JSON; `422` for a negative amount, 3 decimal places, 14 digits, without echoing the value; the lead's example returns every field in [contracts/calculator-api.md](contracts/calculator-api.md) with money as strings and the label; tax year and ATL from the profile; nothing written to the database; no submitted amount appears in the captured logs (`caplog`) or in the attributes of collected telemetry spans, FR-003), then add `POST /api/tax/calculator` to `backend/app/tax/router.py` with `current_user`, `require_profile`, `require_json`, a Pydantic request model (decimal strings, ≥ 0, ≤ 2 places, ≤ 13 digits, default "0") and response model
- [X] T013 [P] [US1] Write `frontend/src/api/calculator.test.ts`, then `frontend/src/api/calculator.ts` (`calculateTax(body)` through `src/api/client.ts`; types matching the contract)
- [X] T014 [US1] Write `frontend/src/pages/CalculatorPage.test.tsx` (fields labelled salary per month, bonus per year, rent per month, dividends per year, bank profit per year, using `MoneyInput`; Calculate shows per-income lines, total, table and the salary share, monthly salary tax and take-home, effective rate, bonus impact; label always visible; amounts shown as given, no maths in the page), then create `frontend/src/pages/CalculatorPage.tsx`, its `/calculator` route under `RequireAuth` in `frontend/src/App.tsx`, and a "Calculator" link in `frontend/src/components/MainNav.tsx` (update `AppFrame.test.tsx`'s link list)

**Checkpoint**: the lead's example works end to end in the browser.

---

## Phase 4: User Story 2 - Dividends and bank profit (Priority: P2)

**Goal**: dividends (15%) and bank profit (20%) taxed as final, kept out of taxable income, with the filer vs non-filer comparison.

**Independent Test**: [quickstart.md](quickstart.md), by-hand steps 2 and 4.

- [X] T015 [P] [US2] Extend `test_calculator_examples.py` to the remaining examples, asserting `dividend_tax`, `profit_tax`, `total_tax`, `filer_comparison` and `blocked_reason` (`profit_over_limit`)
- [X] T016 [US2] Add to `calculator.py`: dividend tax and profit tax (R4, R5; `IncomeLine.treatment` "final" / "separate"), excluded from taxable income; `profit_over_limit` above 5,000,000 with no figures; `FilerLine` per dividends / bank profit (deduction at the user's rate and at the other ATL status's rate, Tenth Schedule rule 1, and the difference); T015 passes
- [X] T017 [US2] Extend `test_calculator_api.py` (dividends for an ATL and a non-ATL profile; bank profit over the limit gives the blocked shape) and `CalculatorPage.test.tsx` (dividend and profit lines; the comparison worded as amounts deducted, never "refund"; the blocked message), then update `CalculatorPage.tsx`

---

## Phase 5: User Story 3 - Every line explained, honest limits (Priority: P3)

**Goal**: every line names its rule, source and effective date; refusals and the not-covered list.

**Independent Test**: [quickstart.md](quickstart.md), by-hand step 3; each step's `rule_location`.

- [X] T018 [P] [US3] Write tests in `test_calculator_examples.py` / `test_calculator_api.py`: every step's `rule_location` names the Ordinance, the section or schedule entry, its pages and "effective 2025-07-01"; `no_income` when every amount is zero (no figures, `steps` empty, `not_covered` and `label` present); `not_covered` equals the list in [data-model.md](data-model.md)
- [X] T019 [US3] Implement in `calculator.py` (wording in `backend/app/tax/calculator_words.py` if it grows, like `breakdown.py`): `no_income`, the fixed not-covered list, blocked messages in the router; T018 passes
- [X] T020 [US3] Extend `CalculatorPage.test.tsx` (the breakdown lists each step with its source; "enter at least one income"; the not-covered note), then update `CalculatorPage.tsx`; the monthly view always says any other tax is "settled with your return" *(Ruling 2026-11-14: deciding when the full tax exceeds 12 × the monthly deduction would be maths in the page, Principle I; the note is shown whenever there is a monthly view)*

---

## Phase 6: Polish & Cross-Cutting

- [X] T021 [P] Add `e2e/tests/calculator.spec.ts`: sign in with a profile, open the calculator, enter the lead's example, see total tax Rs 1,107,600 and the label (fake Gemini not needed)
- [X] T022 [P] Document the calculator in `backend/CLAUDE.md` (tax engine section: `calculator.py`, `calculator_examples.yaml`, the s.8 rule) and the README's feature list
- [X] T023 Run every check and report the results: `docker compose exec backend pytest`, `uv run ruff format`, `pylint`, `mypy`, `lint-imports`; `npm test`, `npm run lint`, `npx tsc -b`, `npx prettier --check .`; `uv run --project backend python scripts/validate_contracts.py --feature 010`
- [X] T024 (manual) Run [quickstart.md](quickstart.md)'s by-hand steps in the browser
- [X] T025 Review with the `backend-reviewer` and `frontend-reviewer` agents and the `code-review` skill (call out the guarded rates change); then `/speckit-converge` and `/speckit-analyze`; fix or record each finding
- [X] T026 (manual) In the PR (linked to the `[010]` issue), raise research R5: s.8(1)(a) answers 004's provisional `salary_share_ambiguous` / `surcharge_ambiguous` refusals; and call out T006's correction of 004's page citations (figures unchanged)

---

## Dependencies & Execution Order

- T001 → T006 (page-number correction). T002 → T003 → every test in Phases 3–5.
- T005 → T006; T007 and T008 before T010; T008a (the lead's OK) before any code in Phase 3.
- US1 (T009–T014) before US2 and US3, which extend the same files (`calculator.py`, the API test, the page); US2 and US3 can then go in either order.
- Polish after the stories; T026 when opening the PR.

## Parallel Opportunities

- Phase 2: T004, T005, T008 together, while T003 is being signed.
- US1: T009 and T013 together; T012 after T010–T011.
- Polish: T021 and T022 together.

## Implementation Strategy

MVP = Phase 2 + US1: the lead's own example (salary + rent) working with its breakdown. Then US2
(dividends, bank profit), then US3 (sources on every line, refusals, not-covered note), then
polish. One pull request at the end (the user's preference), stacked on #44.

GitHub issues for these tasks are titled `[010] T0NN: <description>`; the feature itself is
tracked by the `[010]` issue (T008a).

## Phase 7: Convergence

- [ ] T027 (manual) CRITICAL: get the lead's review of spec.md, plan.md and research.md (the readings to confirm: rent in the slabs with the 75% test, the bonus cliff, s.8(1)(a)) in the PR before merge, and record his approval there per Constitution, Development Workflow ("Review before build") (contradicts)
- [X] T028 Amend spec.md User Story 3, scenario 1, to say the effective rate, monthly view and bonus impact follow the total-tax line, as calculator.py orders them per US3/AC1 (partial)
