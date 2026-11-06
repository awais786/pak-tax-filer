# Feature Specification: Telemetry, Guardrails and PDF Export

**Feature Branch**: `008-telemetry-guardrails-pdf`

**Created**: 2026-11-04

**Status**: Draft

**Input**: README milestone 8: "Telemetry, guardrail tests, CI (lint/type-check/tests + an
eval-accuracy gate), PDF export with the validation-status banner." CI is in feature 001 and the
eval gates in 003 and 006. Source design:
`docs/superpowers/specs/2026-11-04-telemetry-guardrails-pdf-design.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export a result as a labelled PDF (Priority: P1)

A user with a tax result or a wealth statement downloads it as a PDF. Every page carries a banner
saying it isn't practitioner-reviewed or tax advice, that it uses demo data, and what was
validated: that the figures come from confirmed certificates and any rule-check warnings.

**Why this priority**: the only user-facing part of the milestone, and the constitution requires
every exported report to carry an unmissable label.

**Independent Test**: with a synthetic user's tax result and wealth statement, download both PDFs
and check every page has the banner with the right validation status and that the figures match
the screen.

**Acceptance Scenarios**:

1. **Given** a calculated tax result, **When** the user downloads it, **Then** the PDF shows the
   figures, the step-by-step breakdown with rule locations and the separate balances, matching the
   Tax page.
2. **Given** a wealth statement with a result, **When** the user downloads it, **Then** the PDF
   shows the rows, the reconciliation and the result in words, matching the Wealth page.
3. **Given** any exported PDF, **When** any page is read, **Then** it carries "Not yet reviewed by
   a tax practitioner. Not tax advice.", "Demo data only." and the validation status.
4. **Given** a tax result whose certificates have rule-check warnings, **When** exported, **Then**
   the banner says the figures are from confirmed certificates and lists the warnings; with none it
   says "No warnings".
5. **Given** a wealth statement, **When** exported, **Then** the banner says salary figures are from
   confirmed certificates and other rows were entered by the user, and lists any provisional notes.
6. **Given** a workflow result (feature 007), **When** exported, **Then** the banner also says
   "Approved by you on [date]".
7. **Given** a blocked or not-ready result, **When** the user looks for the download, **Then** it is
   unavailable with the reason.

---

### User Story 2 - Guardrails proven across the whole app (Priority: P2)

A developer runs one suite that proves the constitution's guardrails hold everywhere: no AI-made
number reaches a result (I), nothing unconfirmed is used and the workflow can't skip approval
(III), and output is honest and labelled (IV). It runs automatically on every change.

**Why this priority**: the constitution requires automated proof of Principles I, III and IV;
per-feature tests exist but none covers the whole app.

**Independent Test**: break each guardrail on purpose in a throwaway change (e.g. let the tax
engine use the AI library, let an unconfirmed certificate through) and check the suite fails each
time; restore and check it passes.

**Acceptance Scenarios**:

1. **Given** an AI that returns made-up numbers, **When** tax, wealth and workflow results are
   produced, **Then** none of those numbers appears in a result.
2. **Given** the tax engine, tax rates or wealth reconciliation code, **When** it is checked,
   **Then** it does not use the AI library.
3. **Given** an unconfirmed certificate, **When** the tax page, wealth page, assistant tools or
   workflow read a user's figures, **Then** it is never included.
4. **Given** the workflow, **When** a calculation is attempted without approval for the current
   inputs, **Then** it is refused.
5. **Given** assistant questions inside and outside the corpus, **When** answered, **Then** inside
   answers are cited and outside ones refused.
6. **Given** every result the system returns and every PDF page, **When** checked, **Then** the
   practitioner label is present.
7. **Given** any change to the project, **When** the automated checks run, **Then** the guardrail
   suite runs and blocks the change if it fails.

---

### User Story 3 - See how the app and its AI behave (Priority: P3)

A developer sees, for each request and each AI call, how long it took, which model was used, its
token use, and whether its check passed, failed and was replaced, timed out or fell back, with no
user content recorded.

**Why this priority**: helps keep the AI parts reliable and affordable, but users are unaffected.

**Independent Test**: run a synthetic user through upload, tax, assistant and workflow, then check
each request and AI call appears with timing, model, tokens and outcome, and that searching the
recorded data finds no prompt, reply, figure, email, user id or document id.

**Acceptance Scenarios**:

1. **Given** any backend request, **When** it completes, **Then** its route (without ids), duration
   and status are recorded.
2. **Given** any AI call (extraction, tax summary, wealth summary, assistant, workflow agent),
   **When** it completes, **Then** its feature, model, duration, tokens and outcome are recorded.
3. **Given** the recorded data, **When** searched, **Then** it contains no prompt, reply, document
   content, figure, email, user or session id, or database query text.
4. **Given** no viewer has been set up, **When** the app runs, **Then** the data goes to the logs;
   once a viewer is approved and switched on, it goes there instead.

### Edge Cases

- A tax result that the engine blocks (e.g. provisional rule): no PDF; the reason is shown.
- A PDF long enough to span several pages: the banner repeats on every page.
- An AI call that fails before returning: recorded with outcome "fallback" and no tokens.
- The workflow's inputs changed after approval: its PDF is unavailable until approved again.
- A guardrail rule broken by a change in a feature other than the one being edited: the suite
  still catches it (it covers the whole app).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to download their tax result and their wealth statement as PDFs
  from the Tax and Wealth pages, and the workflow's result as the tax PDF.
- **FR-002**: Every page of every PDF MUST carry "Not yet reviewed by a tax practitioner. Not tax
  advice.", "Demo data only." and the validation status (Principle IV).
- **FR-003**: The tax PDF's validation status MUST say the figures are from confirmed certificates
  and list feature 003's rule-check warnings on those certificates, or "No warnings"; the workflow
  version MUST add the approval date.
- **FR-004**: The wealth PDF's validation status MUST say salary figures are from confirmed
  certificates and other rows were entered by the user, and list feature 005's provisional notes,
  or "No warnings".
- **FR-005**: PDFs MUST contain only figures computed by code, code-written messages and
  retrieved passages with citations; no AI-written text.
- **FR-006**: PDFs MUST match the on-screen result, be generated on each request, and never be
  stored.
- **FR-007**: Blocked or not-ready results, and workflow results not approved for the current
  inputs, MUST NOT be exportable; the reason MUST be shown.
- **FR-008**: One guardrail suite MUST prove Principle I (no AI-made number in any tax, wealth or
  workflow result; the engine, rates and reconciliation never use the AI library), Principle III
  (no unconfirmed certificate reaches the tax page, wealth page, assistant tools or workflow; no
  workflow calculation without approval for the current inputs) and Principle IV (assistant
  answers cited, out-of-corpus refused, label on every result and PDF page).
- **FR-009**: The guardrail suite MUST run automatically on every change and block it on failure.
- **FR-010**: The system MUST record each backend request's route without ids, duration and
  status, and database call timings.
- **FR-011**: The system MUST record each AI call's feature, model, duration, tokens and outcome
  (passed, check failed and replaced, timed out, fallback).
- **FR-012**: Recorded data MUST NOT contain prompts, replies, document contents, figures, emails,
  user or session ids, raw paths with ids, or database query text (Principle V).
- **FR-013**: Recorded data MUST go to the logs by default and to a local viewer once one is
  approved and switched on by a setting.
- **FR-014**: The feature MUST NOT include usage analytics, alerting, hosted dashboards, filing
  forms, or emailing or storing PDFs.

### Key Entities

- **PDF export**: a generated document for one user's tax result, workflow result or wealth
  statement: content, banner (label, demo notice, validation status), generation date. Not stored.
- **Telemetry record**: one request or AI call: route or feature, model, duration, tokens,
  outcome, time. No user content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pages in every exported PDF carry the label, demo notice and validation
  status (verified by reading the PDFs back in tests).
- **SC-002**: A user downloads a PDF within 5 seconds of clicking.
- **SC-003**: Every deliberate break of Principles I, III or IV in a test change makes the
  guardrail suite fail (100% of planted breaks caught).
- **SC-004**: 100% of AI calls in a full synthetic run appear in telemetry with model, tokens and
  outcome.
- **SC-005**: 0 occurrences of prompts, replies, figures, emails, user ids or document ids in the
  recorded data of a full synthetic run.

## Assumptions

- CI (001) and the eval gates (003, 006) already exist; this feature adds only the guardrail job.
- Builds on 004 (tax result, breakdown, label), 005 (wealth statement, provisional notes), 003
  (rule-check warnings), 006 (assistant, MCP tools), 007 (workflow approval) and 002 (profile:
  tax year).
- The local viewer is a new component needing the lead's approval (constitution); until then,
  logs are used and nothing is blocked.
- Synthetic data only (Principle V).
