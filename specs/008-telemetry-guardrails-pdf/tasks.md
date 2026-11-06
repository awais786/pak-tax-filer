---

description: "Task list for feature 008: Telemetry, Guardrails and PDF Export"
---

# Tasks: Telemetry, Guardrails and PDF Export

**Input**: Design documents from `/specs/008-telemetry-guardrails-pdf/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–007 implemented. Jaeger tasks (T020) only after **the lead's approval** is recorded
in `plan.md`; everything else proceeds without it.

**Tests**: written first for the PDF banner (Principle IV), every guardrail (I, III, IV) and the
"no user content" telemetry rule (Principle V).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US3)

---

## Phase 1: Setup

- [ ] T001 Add `weasyprint`, `jinja2`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy` and `opentelemetry-exporter-otlp` to `backend/pyproject.toml` with `uv add`, and `import-linter` as a dev dependency; install WeasyPrint's system packages (Pango, HarfBuzz) in `backend/Dockerfile`
- [ ] T002 [P] Add `OTEL_EXPORTER` (default `console`) and `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://jaeger:4317`) to `backend/app/settings.py`

---

## Phase 2: Foundational (blocking)

- [ ] T003 Create `backend/app/reports/status.py` per research R7: validation-status lines for tax, wealth and workflow PDFs from 003's `rules.py` warnings, 005's provisional notes and 007's `approved_at`, with `backend/tests/reports/test_status.py` covering warnings, "No warnings" and the approval line

**Checkpoint**: banner text can be built for every PDF type.

---

## Phase 3: User Story 1 - Export a result as a labelled PDF (Priority: P1) 🎯 MVP

**Goal**: tax, wealth and workflow PDFs with the banner on every page (FR-001 to FR-007).

**Independent Test**: [quickstart.md](quickstart.md) scenario 1.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T004 [P] [US1] Write `backend/tests/reports/test_pdfs.py` per [contracts/pdf-and-telemetry.md](contracts/pdf-and-telemetry.md), reading PDFs back with `pypdf`: tax, wealth and workflow PDFs return `application/pdf` with the attachment filename; every page (including a forced multi-page wealth statement) contains "Not yet reviewed by a tax practitioner. Not tax advice.", "Demo data only." and the validation status from T003; figures equal the JSON results; no text from the fake summary clients appears (FR-005); blocked tax, not-ready wealth and unapproved workflow → `409` with the reason; another user's data is never exported
- [ ] T005 [P] [US1] Write `frontend/src/components/DownloadPdfButton.test.tsx`: downloads on click; disabled with the reason when the result is blocked, not ready or not approved

### Implementation for User Story 1

- [ ] T006 [US1] Create `backend/app/reports/templates/base.html` (CSS running header banner on every page, research R6), `tax.html` and `wealth.html`, and `backend/app/reports/render.py` (Jinja2 → WeasyPrint `write_pdf`)
- [ ] T007 [US1] Create `backend/app/reports/router.py` with `GET /api/tax/{tax_year}/pdf`, `GET /api/wealth/{tax_year}/pdf` and `GET /api/workflow/result/pdf` using 004's, 005's and 007's existing result functions and protections; include in `backend/app/main.py`; T004 passes
- [ ] T008 [US1] Create `frontend/src/components/DownloadPdfButton.tsx` and add it to `frontend/src/pages/TaxPage.tsx`, `WealthPage.tsx` and the result step of `WorkflowPage.tsx`; T005 passes
- [ ] T009 [US1] Run [quickstart.md](quickstart.md) scenario 1, including the 5-second check (SC-002)

**Checkpoint**: labelled PDFs download from every result screen.

---

## Phase 4: User Story 2 - Guardrails proven across the whole app (Priority: P2)

**Goal**: one suite and import rules for Principles I, III and IV, run in CI (FR-008, FR-009).

**Independent Test**: [quickstart.md](quickstart.md) scenario 2.

- [ ] T010 [P] [US2] Create `.importlinter` with forbidden contracts per research R4 (`app.tax.engine`, `app.tax.rates`, `app.wealth.reconcile` may not import `anthropic`, `app.documents.extraction`, `app.rag`, `app.workflow.agents`); `lint-imports` passes
- [ ] T011 [P] [US2] Write `backend/tests/guardrails/test_principle_1.py` per research R5: fake clients from 003–007 return made-up numbers; tax, wealth and workflow results equal the worked-example values
- [ ] T012 [P] [US2] Write `backend/tests/guardrails/test_principle_3.py`: a user with one confirmed and one `needs_review` certificate; the unconfirmed one is absent from `GET /api/tax`, `GET /api/wealth`, `calculate_income_tax` and the workflow gate; `GET /api/workflow/result` and its PDF without approval → `409`
- [ ] T013 [P] [US2] Write `backend/tests/guardrails/test_principle_4.py`: assistant answers in corpus are cited and out-of-corpus are refused (fake client); every result endpoint returns the label; every PDF page carries the banner
- [ ] T014 [US2] Create `backend/tests/guardrails/README.md` listing what each file proves and the related per-feature tests (005 `test_reconcile_imports.py`, 006 `test_mcp_tools.py`, 007 `test_gate.py`, 004 T013 and 005 T011 screen label tests)
- [ ] T015 [US2] Add job `guardrails` to `.github/workflows/ci.yml` (on every pull request and push to `main`): `lint-imports`, then `pytest tests/guardrails`
- [ ] T016 [US2] Run [quickstart.md](quickstart.md) scenario 2, including the three planted breaks (one per principle, SC-003)

**Checkpoint**: breaking any guardrail fails CI.

---

## Phase 5: User Story 3 - See how the app and its AI behave (Priority: P3)

**Goal**: request, database and AI-call telemetry with no user content (FR-010 to FR-013).

**Independent Test**: [quickstart.md](quickstart.md) scenario 3.

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T017 [P] [US3] Write `backend/tests/telemetry/test_spans.py` with an in-memory span exporter: a request gives a span named by route template; each of the seven `app.feature` values appears with `gen_ai.request.model`, token counts and `app.outcome` (`passed`, `check_failed`, `timeout`, `fallback` all exercised via fake clients); `OTEL_EXPORTER=otlp` selects the OTLP exporter and the default selects console (FR-013)
- [ ] T018 [P] [US3] Write `backend/tests/telemetry/test_no_content.py`: after a synthetic run (upload, tax, ask, workflow), no span attribute or name contains the demo email, a user or document id, a figure, prompt or reply text, or SQL text (SC-005)

### Implementation for User Story 3

- [ ] T019 [US3] Create `backend/app/telemetry/setup.py` (tracer provider, console or OTLP exporter from `OTEL_EXPORTER`, FastAPI instrumentation with route templates, SQLAlchemy instrumentation with statement text dropped, research R1–R2) and `backend/app/telemetry/ai.py` (`ai_call(feature, model)`, research R3); call it from 003's `extraction/client.py`, 004's and 005's `summary.py`, 006's `rag/answer.py` and 007's `workflow/agents.py`; T017 and T018 pass
- [ ] T020 [US3] **After the lead's approval:** add `jaeger` (all-in-one, profile `telemetry`, ports 4317 and 16686) to `docker-compose.yml`; record the approval in `plan.md`
- [ ] T021 [US3] Run [quickstart.md](quickstart.md) scenario 3

**Checkpoint**: all three stories work.

---

## Phase 6: Polish

- [ ] T022 [P] Add "Telemetry" and "PDF export" sections to `backend/CLAUDE.md`: wrap every Claude call in `ai_call`; never add content attributes; PDFs only through `app/reports` templates with the banner
- [ ] T023 Run the lint, format and type checks (001's CI), both test suites, the guardrails job and all of [quickstart.md](quickstart.md); record results in the PR description

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003)** → stories.
- **US1** needs T003. **US2**'s Principle IV test (T013) checks PDFs, so it follows US1; T010–T012
  can start alongside US1. **US3** is independent of US1/US2.
- T020 waits for the lead's approval; nothing else depends on it.
- `WorkflowPage.tsx`, `TaxPage.tsx` and `WealthPage.tsx` are edited only by T008.

## Parallel Opportunities

- T002 alongside T001; US1 tests T004, T005 together.
- US2 T010–T012 together (T013 follows US1, which builds the PDFs it checks); US3 tests T017,
  T018 together; US3 can run alongside US1.

## Implementation Strategy

1. **MVP = User Story 1**: labelled PDFs (the constitution's export rule).
2. **Add US2**: the guardrail suite and CI job.
3. **Add US3**: telemetry; Jaeger once approved.
4. **Polish**, then one implementation PR. With this, features 001–008 complete the MVP.

GitHub issues for these tasks are titled `[008] T0NN: <description>`.
