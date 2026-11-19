# Feature Specification: Deterministic Tax Engine

**Feature Branch**: `004-tax-engine`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Deterministic tax engine (README milestone 4). Calculate a salaried user's TY2026 tax from their confirmed certificates and ATL status: salaried slab tax, §4AB surcharge, §7B tax on bank profit, credits for tax already deducted, payable or over-deducted results, §219 rounding, exact decimal arithmetic. Every rate from FBR law text with its source, stored per tax year. An authoritative step-by-step breakdown always shown, plus an AI summary shown only if every number in it matches. Provisional rules pending the lead. Hand-verified worked examples signed off before engine code." Source design: `docs/superpowers/specs/2026-11-03-tax-engine-design.md`, which lists every rule's exact location in the Income Tax Ordinance, 2001 as amended up to 31.07.2025.

## Clarifications

### Session 2026-11-03

- Q: If the salary side shows tax payable but the profit side shows extra tax withheld (or vice versa), should the app combine them into one balance? → A: No. Salary and profit balances are shown separately with no combined total; whether they can be set off is asked of the lead (provisional).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See my tax and whether I owe or overpaid (Priority: P1)

A salaried user whose certificates are confirmed opens the tax page and, using the ATL status
from their taxpayer profile (feature 002), sees their TY2026 tax: tax on salary, any surcharge, tax
on bank profit, the tax already taken by their employer and bank, and whether they owe more or
had too much taken.

**Why this priority**: this is the product's central promise; everything before it collects the
inputs.

**Independent Test**: with confirmed synthetic certificates whose correct results were worked out
by hand from the Ordinance, set ATL status in the profile, open the tax page, and compare every figure shown with the
hand-worked result.

**Acceptance Scenarios**:

1. **Given** confirmed salary certificates with summed taxable salary in any band of the
   salaried table, **When** the user views their tax, **Then** the salary tax equals the band's
   fixed amount plus its rate on the amount above the band's lower limit, exactly as in the
   Ordinance's table.
2. **Given** taxable income above Rs 10 million, **When** the tax is shown, **Then** a surcharge
   of 9% of the salary tax is added.
3. **Given** confirmed bank profit certificates with summed profit up to Rs 5 million, **When**
   the tax is shown, **Then** the profit tax is 20% of the gross profit.
4. **Given** tax deducted by employers and withheld by banks, **When** results are shown, **Then**
   the salary side shows (salary tax + surcharge) minus tax deducted as **payable** or
   **over-deducted**, and the profit side compares profit tax with tax withheld.
5. **Given** several confirmed certificates of the same type, **When** the tax is calculated,
   **Then** their figures are summed.
6. **Given** any amount with a fraction of a rupee, **When** final tax and balances are shown,
   **Then** fractions under 50 paisa are dropped and 50 paisa or more round up to one rupee.
7. **Given** any result, **When** it is shown, **Then** a clear "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.

---

### User Story 2 - Understand every step (Priority: P2)

The user sees exactly how each figure was reached, step by step, with the source rule for each
step, and may also see a short plain-language summary that never contradicts the steps.

**Why this priority**: an unexplained tax figure can't be checked or trusted; the README requires
a step-by-step explanation.

**Independent Test**: for a hand-worked example, check that every step shown matches the
hand-working and names its rule; then give the summary check a summary containing a wrong number
and confirm the summary is not shown.

**Acceptance Scenarios**:

1. **Given** a calculated result, **When** the user views it, **Then** a step-by-step breakdown
   shows each step's inputs, rule, source location and result.
2. **Given** a calculated result, **When** a plain-language summary is produced, **Then** it is
   shown only if every number in it appears in the breakdown.
3. **Given** a summary containing any number not in the breakdown, or the summary service is
   unavailable, **When** the result is shown, **Then** only the breakdown is shown.

---

### User Story 3 - Honest limits (Priority: P3)

When the law is unclear for the user's situation, or required inputs are missing, the app says so
instead of producing a number.

**Why this priority**: overstating certainty is the most harmful failure (constitution, Principle
IV); these rules are provisional until the lead confirms them.

**Independent Test**: try each blocked case and confirm the message and that no tax figure is
shown.

**Acceptance Scenarios**:

1. **Given** the user has no taxpayer profile, or no confirmed salary certificate exists, **When** the
   user opens the tax page, **Then** they are told what is missing and no calculation is shown.
2. **Given** summed bank profit above Rs 5 million, **When** the tax is requested, **Then** the
   user is told this case isn't supported yet, and no figure is shown.
3. **Given** salary is more than 75% of taxable income when bank profit is left out but not when
   it is included (or the same disagreement about the Rs 10 million surcharge limit), **When** the
   tax is requested, **Then** the user is told their situation needs a tax practitioner, and no
   figure is shown.
4. **Given** a user not on the ATL whose bank withheld more than the profit tax, **When** results
   are shown, **Then** the difference is labelled "extra tax withheld; whether it can be reclaimed
   needs confirmation", never "refund".

---

### User Story 4 - Rates are traceable and correct (Priority: P4)

A reviewer can see, for every rate the app uses, the FBR document, location and Finance Act it
came from, and automated checks catch rate-table typos.

**Why this priority**: required by Principle II; invisible to users but protects every result.

**Independent Test**: list the stored rates and confirm each has its source; change one band's
fixed amount by 1 rupee and confirm the consistency check fails.

**Acceptance Scenarios**:

1. **Given** the stored rates for a tax year, **When** they are inspected, **Then** each shows its
   source document, location and the Finance Act that set it.
2. **Given** the salaried table, **When** checked automatically, **Then** each band's fixed amount
   equals the tax at the top of the previous band.
3. **Given** a new tax year's rates, **When** added, **Then** no change to the calculation itself
   is needed.

### Edge Cases

- Taxable salary exactly on a band limit (e.g. Rs 600,000, Rs 1,200,000): uses the lower band, as
  the table says "does not exceed".
- Taxable income exactly Rs 10,000,000: no surcharge ("exceeds").
- Bank profit exactly Rs 5,000,000: supported ("exceeds" triggers the limit).
- No bank certificates: profit side shows zero.
- Tax deducted equals tax due: balance shown as zero.
- Salary side payable while profit side over-withheld (or the reverse): both shown separately;
  no combined figure.
- A confirmed certificate is deleted after a calculation: the next view recalculates from what is
  confirmed now; results are never stored as final.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST calculate TY2026 salary tax using the salaried table in First
  Schedule, Part I, Division I, clause (2) of the Ordinance as amended by the Finance Act 2025.
- **FR-002**: The system MUST add a 9% surcharge on the salary tax when taxable income exceeds
  Rs 10 million (§4AB).
- **FR-003**: The system MUST calculate tax on bank profit at 20% of gross profit (§7B with
  Division IIIA(a)).
- **FR-004**: Inputs MUST come only from confirmed certificates (feature 003), summed per type,
  plus the ATL status in the user's taxpayer profile (feature 002).
- **FR-005**: The system MUST show salary-side and profit-side results: tax, credits and the
  balance as payable or over-deducted. The two balances MUST NOT be combined into one total.
  *(Provisional, pending the lead.)*
- **FR-006**: Calculations MUST use exact decimal arithmetic; final amounts MUST be rounded per
  §219.
- **FR-007**: No tax figure MUST be produced, adjusted or checked by an AI (constitution,
  Principle I).
- **FR-008**: Every rate MUST be stored as data for its tax year with its source document,
  location and Finance Act; adding a tax year MUST NOT require changing the calculation.
- **FR-009**: An automated check MUST verify that each salaried band's fixed amount equals the tax
  at the top of the previous band.
- **FR-010**: The system MUST show a step-by-step breakdown for every result, each step naming
  its rule and source.
- **FR-011**: An AI-written summary MAY be shown only when every number in it appears in the
  breakdown; otherwise it MUST be omitted. *(Removed 2026-11-16, the lead: no AI where no
  reasoning is needed. There is no AI summary; the breakdown (FR-010) explains every figure. Amended again 2026-11-16:
  a short summary written by code from the result's own amounts, never the two sides added
  together, and none when blocked; design `docs/superpowers/specs/2026-11-16-plain-summary-design.md`.)*
- **FR-012**: The system MUST refuse to calculate, with a reason, when the user has no taxpayer profile,
  no confirmed salary certificate exists, summed bank profit exceeds Rs 5 million, or the 75%
  salary condition or the Rs 10 million surcharge limit gives different answers with and without
  bank profit. *(The last three are provisional, pending the lead.) Amended 2026-11-17: the last
  two are removed. Bank profit under s.7B is a final tax outside taxable income (s.8(1)(a); feature
  010, research R5), so the 75% test and the surcharge limit use salary alone and never disagree.*
- **FR-013**: For users not on the ATL, any bank withholding above the profit tax MUST be labelled
  "extra tax withheld; whether it can be reclaimed needs confirmation". *(Provisional.)*
- **FR-014**: Every result MUST carry a visible "not yet practitioner-reviewed; not tax advice"
  label.
- **FR-015**: Worked examples covering every band, every boundary in the Edge Cases, the
  surcharge, the Rs 5 million limit, rounding and multiple certificates MUST be verified by hand
  against the Ordinance and signed off before the calculation is built, and MUST become its
  tests.

### Key Entities

- **Tax-year rates**: the rules for one tax year: salaried bands, surcharge rate and limit,
  profit-on-debt rate and limit, rounding rule; each with source document, location and Finance
  Act.
- **Tax inputs**: summed taxable salary, tax deducted, gross bank profit, tax withheld, ATL status,
  tax year.
- **Tax result**: salary tax, surcharge, profit tax, credits, balances, the step-by-step breakdown,
  any blocking reason, and the optional verified summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the signed-off worked examples produce exactly the hand-worked figures, to
  the rupee.
- **SC-002**: 100% of stored rates show their source document, location and Finance Act.
- **SC-003**: 0 summaries containing a number absent from the breakdown are ever shown (tested
  with deliberately wrong summaries).
- **SC-004**: A user with confirmed certificates sees their result within 5 seconds of opening
  the tax page.
- **SC-005**: Every blocked case in User Story 3 shows a reason and no tax figure.

## Assumptions

- The certificate's taxable salary is used as stated; analysing allowances or exemptions is out
  of scope.
- MVP users are resident salaried individuals whose only income is salary and bank profit.
- ATL status comes from the user's taxpayer profile (feature 002); the tax page does not ask it
  (amended 2026-11-04).
- Rates are from the Ordinance as amended up to 31.07.2025 (TY2026). FBR Circular 01 of 2025-26
  has two wrong slab amounts and is not used as a source.
- The three provisional rules are asked of the lead in the pull request and may change.
- Out of scope: other income, deductions and tax credits, pension, non-bank profit on debt, other
  tax years' data, filing.
