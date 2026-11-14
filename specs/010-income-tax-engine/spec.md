# Feature Specification: Simple Income Tax Calculator

**Feature Branch**: `010-income-tax-engine`

**Created**: 2026-11-13 (cut down to the simple calculator 2026-11-14)

**Status**: Draft

**Input**: User description: "Basic scenarios on the side: the user can just pass info like
salary, dividend, bonus, rental and you show him tax info; behind the scene some basic formulas"
(the lead, 2026-11-14; asked whether to keep it basic rather than his earlier full-engine prompt,
he answered "Simple"). Source design:
`docs/superpowers/specs/2026-11-13-full-income-tax-engine-design.md`. Constitution 1.3.0.

## Clarifications

### Session 2026-11-14

- Q: Should the calculator need a signed-in user with a taxpayer profile, or be open to anyone
  with a filer/non-filer choice on the form? → A: Signed in with a profile; ATL status and tax
  year come from the profile (no filer/non-filer choice on the form).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Type my incomes, see my tax (Priority: P1)

A signed-in user with a taxpayer profile opens the Tax calculator, types their salary per month,
any bonus for the year and any rent per month, and sees the tax on each, the total, which table
applies and why, and how each figure was worked out.

**Why this priority**: it is the lead's own example (salary Rs 250,000 a month and rent
Rs 140,000 a month) and the core of what he asked for.

**Independent Test**: enter the signed worked examples for salary, bonus and rent and compare
every figure with the hand-worked result.

**Acceptance Scenarios**:

1. **Given** a profile for TY2026, **When** the user opens the Tax calculator, **Then** they see
   fields for salary per month, bonus per year, rent per month, dividends per year and bank profit
   per year, each optional.
2. **Given** salary Rs 250,000 a month and rent Rs 140,000 a month, **When** the user calculates,
   **Then** the result shows yearly salary Rs 3,000,000 and rent Rs 1,680,000, and every figure
   matches the signed worked example for that case to the rupee.
3. **Given** a bonus, **When** the user calculates, **Then** it is taxed as salary, with the
   monthly salary × 12, under the salaried or non-salaried table.
4. **Given** rent, **When** the user calculates, **Then** it is taxed under the treatment the
   Ordinance sets for an individual in TY2026, as its own line.
5. **Given** any inputs, **When** the result is shown, **Then** it states which table applies, the
   salary share used for the 75% test and which incomes it counted, as the Ordinance sets them.
6. **Given** any result, **When** it is shown, **Then** the "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.
7. **Given** a salary, **When** the result is shown, **Then** a monthly view shows the tax on the
   monthly salary per month and the take-home pay per month (monthly salary minus that tax), with
   the bonus left out of both.
8. **Given** any result, **When** it is shown, **Then** the effective rate (total tax as a
   percentage of total yearly gross income, rent before the repairs allowance, one decimal place)
   is shown.
9. **Given** a bonus and a salary, **When** the result is shown, **Then** it shows how the bonus
   changes the total: the tax with the bonus minus the tax without it. It can lower the tax, when
   the bonus lifts salary over 75% (the salaried table is never higher), and the page says so.

---

### User Story 2 - Dividends and bank profit (Priority: P2)

The same user adds dividends and bank profit and sees each taxed under its own treatment.

**Why this priority**: dividends are in the lead's list; bank profit is already in the engine
(feature 004) and costs little to include.

**Independent Test**: enter the signed worked examples for dividends and bank profit, alone and
with salary, and compare every figure.

**Acceptance Scenarios**:

1. **Given** dividends, **When** the user calculates, **Then** they are taxed at the rate and under
   the treatment the Ordinance sets for TY2026 and the user's ATL status, as their own line.
2. **Given** bank profit, **When** the user calculates, **Then** it is taxed as feature 004 does
   (separately at 20%, §7B), as its own line.
3. **Given** incomes taxed separately, **When** the result is shown, **Then** they are kept out
   of the slab income and the breakdown says so.
4. **Given** dividends or bank profit, **When** the result is shown, **Then** a filer vs non-filer
   line shows the amount deducted at source at the user's ATL status and at the other status, and
   the difference, labelled as a comparison of deductions: the tax itself is the same for both.

---

### User Story 3 - Every line explained, honest limits (Priority: P3)

The user sees how each figure was reached, with its rule and source; a case the law leaves to
judgement is shown as such, not as a number.

**Why this priority**: an unexplained or guessed figure can't be trusted (Principles II, IV).

**Independent Test**: for each worked example, check each breakdown line names its rule and
source; try each refused case and confirm the message and that no figure is shown.

**Acceptance Scenarios**:

1. **Given** a result, **When** the user views it, **Then** each line shows its inputs, rule,
   source and result, ending with the total tax; the lines worked out from it (the effective
   rate, the monthly view, the bonus impact) follow it.
2. **Given** bank profit above Rs 5 million (s.7B no longer applies, research R5), **When** the
   user calculates, **Then** they are told this case isn't covered and needs a tax practitioner,
   and no figure is shown.
3. **Given** a result, **When** it is shown, **Then** a short note lists what the calculator does
   not cover (tax deducted, other incomes, deductions and credits).

### Edge Cases

- Every field empty or zero: "enter at least one income"; no figure.
- No taxpayer profile: refused (`409`), as the Tax page does.
- Negative amounts, more than 2 decimal places, or more than 13 digits before the decimal point:
  refused with the field and reason.
- Monthly amounts with paisa: × 12 exactly; only final amounts are rounded (§219).
- Salary exactly 75% of the income the test uses, taxable income exactly on each slab limit,
  exactly on the §4AB Rs 10 million limit, and rent and dividends exactly on any of their limits:
  each pinned by a worked example.
- No salary: no monthly view; no bonus impact without a salary and a bonus. Total income zero is
  impossible (at least one income above zero), so the effective rate always has a divisor.
- Rent changing the table used (the 75% test): the monthly view still taxes the salary alone on
  the salaried table, as an employer deducts (s.149), and the page says the rest is settled with
  the return; the bonus impact recalculates the full result, so a table switch shows in it. Both
  pinned by worked examples.
- No salary at all (e.g. rent only): the non-salaried table applies to any slab income, if the law
  puts any there; pinned by a worked example.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer a Tax calculator, separate from the Tax page, where a signed-in
  user with a profile types salary per month, bonus per year, rent per month, dividends per year
  and bank profit per year, each optional, at least one above zero.
- **FR-002**: Monthly amounts MUST be converted to yearly (× 12); the calculation works on yearly
  amounts.
- **FR-003**: The inputs MUST NOT be stored, logged or sent to any AI; the result is calculated on
  request and never stored.
- **FR-004**: Each income MUST be taxed under its treatment in the Ordinance for TY2026, with the
  75% salary test and the §4AB surcharge applied to the income the Ordinance specifies.
- **FR-005**: The calculation MUST live in feature 004's engine package, sharing its rounding,
  breakdown steps and slab lookup (no second engine); the Tax page's figures MUST not change.
- **FR-006**: Every new rule (rent, dividends, any other) MUST be stored as TY2026 data with its
  source document, section, Finance Act and effective date, from FBR's own documents only.
- **FR-007**: Calculations MUST use exact decimal arithmetic with §219 rounding on final amounts;
  no figure may be produced, adjusted, rounded or checked by an AI.
- **FR-008**: The result MUST show the yearly amount of each income and how it is taxed, the tax on
  each category (salary, bonus and rent share one slab tax; dividends and bank profit each have
  their own), the total tax, the
  table used and why (with the salary share), the slab used, and a breakdown line per step with
  its rule and source.
- **FR-008a**: The result MUST also show: a monthly view (tax on the monthly salary per month and
  take-home pay per month, bonus excluded); the effective rate (total tax ÷ total yearly gross
  income, rent before the repairs allowance, as a percentage to one decimal place); when there is a bonus and a salary, the extra tax the
  bonus causes (tax with it minus tax without it); and when there are dividends or bank profit, a
  filer vs non-filer comparison (the amount deducted at source at each ATL status, and the
  difference; the tax itself doesn't change).
  These are derived from the engine's own figures by plain code, each with a breakdown line.
- **FR-009**: Where the calculator's rules don't cover a case, the system MUST refuse it with
  "needs a tax practitioner" and no figure. The research found one such case for these inputs:
  bank profit above Rs 5 million (`profit_over_limit`); every amount zero is refused as
  `no_income`.
- **FR-010**: Every result MUST carry the practitioner label and a note of what is not covered.
- **FR-011**: ATL status and the tax year MUST come from the taxpayer profile; the form MUST NOT
  ask for them.
- **FR-012**: Worked examples covering each income, every slab and limit the calculator uses, and
  the 75% test on both sides MUST be worked out from the Ordinance, citing their pages, and
  accepted by the author before the code, and become its tests. *(Amended 2026-11-14: the author
  accepted them provisionally, cross-checked by script rather than by hand; they and the rules
  they rest on MUST be revised when a tax practitioner reviews the app.)*

### Key Entities

- **Calculator inputs** (never stored): salary per month, bonus, rent per month, dividends, bank
  profit; plus ATL status and tax year from the profile.
- **TY2026 rules**: added to 004's rates: rent and dividend treatment and rates, each with source
  and effective date.
- **Calculator result** (never stored): per-income amounts and tax, total tax, table and reason,
  slab, the monthly view, effective rate, bonus impact, filer vs non-filer comparison, breakdown
  lines, any refusal reason, the label and the not-covered note.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the signed worked examples produce exactly the hand-worked figures, to the
  rupee.
- **SC-002**: 100% of new rules show their source document, section, Finance Act and effective
  date.
- **SC-003**: A user can type their incomes and see the result in under 1 minute.
- **SC-004**: The Tax page's results for all of 004's worked examples are unchanged.
- **SC-005**: Every refused case shows a reason and no figure.

## Assumptions

- Salary means taxable salary per month as on a payslip; exempt allowances aren't analysed.
- TY2026 only, from the Ordinance amended to 31.07.2025 (Finance Act 2025). How rent and dividends
  are taxed, and whether they count toward the 75% test and the surcharge limit, are settled in
  the plan's research from the Ordinance, never from a third-party calculator.
- Out of scope (the lead's "Simple", 2026-11-14): saving inputs; tax deducted and payable or
  refundable; freelance, business, capital gains and other incomes; deductions and credits; tax on
  bills and advance tax; TY2027; guided filing, PDF, MCP and wealth statement links.
- Synthetic data only (Principle V); the calculator needs sign-in like every page.
- The legal readings in research.md, the page citations and the worked examples are provisional
  until a tax practitioner reviews the app (the author's decision, 2026-11-14); the practitioner
  label on every result already says so to users.
