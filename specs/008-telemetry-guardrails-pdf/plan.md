# Implementation Plan: Telemetry, Guardrails and PDF Export

**Branch**: `008-telemetry-guardrails-pdf` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-telemetry-guardrails-pdf/spec.md`

## Summary

OpenTelemetry instruments FastAPI (route templates), SQLAlchemy (timings, no statement text) and
every Claude call through one wrapper that adds GenAI attributes, the feature and the outcome;
spans go to the logs, or to a local Jaeger when the lead approves it. A `guardrails` CI job runs
`import-linter` contracts and a cross-app pytest suite for Principles I, III and IV. PDFs are
HTML templates rendered by WeasyPrint with the banner as a repeated page header, served by three
`…/pdf` endpoints and read back with `pypdf` in tests. Decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: added (libraries): `opentelemetry-sdk`,
`opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`,
`opentelemetry-exporter-otlp`, `weasyprint`, `jinja2`; dev: `import-linter`. Existing: FastAPI,
SQLAlchemy, `anthropic`, `pypdf` (003). **Jaeger** (Docker service, pending the lead's approval).

**Storage**: none added (PDFs and telemetry are not stored in the database)

**Testing**: pytest with an in-memory span exporter and the fake Claude clients from 003–007;
`pypdf` to read PDFs back; `lint-imports`; Vitest

**Target Platform**: local Docker Compose (from 001); Jaeger under a Compose profile

**Project Type**: web application

**Performance Goals**: PDF within 5 seconds (SC-002); telemetry adds no noticeable delay
(batching exporter)

**Constraints**: no user content in telemetry (FR-012, Principle V); banner on every PDF page
(Principle IV); no AI text in PDFs (FR-005)

**Scale/Scope**: 3 PDF endpoints, 2 templates, 1 CI job, 1 telemetry wrapper used by 5 AI callers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | PDFs hold only code-computed figures; import rules keep `anthropic` out of engine, rates, reconciliation (R4) |
| II. Authoritative sources | PASS | PDFs show 004's rule locations and 006's citations unchanged |
| III. Human confirmation | PASS | Guardrail suite covers every reader of certificates and the workflow gate (R5) |
| IV. Honest output | PASS | Banner on every page (R7), tested by reading PDFs back |
| V. Synthetic data only | PASS | Telemetry has no content, ids, raw paths or SQL text (R2) |
| VI. Test-first, measured AI | PASS | Guardrails written as tests first; AI outcomes measured in telemetry |
| VII. MVP scope | PASS | No analytics, alerting, hosted dashboards or stored PDFs (FR-014) |
| Stack | **PENDING LEAD** for Jaeger only | New Docker service; until approved, the console exporter is used and nothing is blocked. Libraries follow 002's precedent (`pwdlib`) |
| Secrets | PASS | No new secrets |

**Post-design re-check:** PASS, with Jaeger pending the lead's approval.

## Project Structure

### Documentation (this feature)

```text
specs/008-telemetry-guardrails-pdf/
├── plan.md
├── research.md          # R1–R8
├── data-model.md        # telemetry attributes, PDF content (nothing stored)
├── quickstart.md
├── contracts/
│   ├── pdf-and-telemetry.md
│   └── api.yaml         # machine-checked once feature 001 US5 (PR #17) builds the checker
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
docker-compose.yml                    # + jaeger (profile "telemetry")
.importlinter                         # Principle I import contracts
.github/workflows/ci.yml              # + guardrails job
backend/
├── Dockerfile                        # + Pango packages for WeasyPrint
├── app/telemetry/
│   ├── setup.py                      # providers, exporter choice, instrumentation
│   └── ai.py                         # ai_call() span wrapper
├── app/reports/
│   ├── render.py                     # HTML → PDF
│   ├── status.py                     # validation status per PDF type
│   ├── router.py                     # …/pdf endpoints
│   └── templates/base.html, tax.html, wealth.html
└── tests/
    ├── telemetry/test_spans.py, test_no_content.py
    ├── reports/test_pdfs.py
    └── guardrails/README.md, test_principle_1.py, test_principle_3.py, test_principle_4.py
frontend/src/components/DownloadPdfButton.tsx (+ test)
```

**Structure Decision**: telemetry and reports are their own packages so existing features only
change where they call Claude (one wrapper) or add a button; guardrails live in one folder with
their own CI job.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Jaeger service (pending lead approval) | A local viewer for traces (README "telemetry"; learning goal) | Logs only: hard to read across a request; hosted tools: third party, Principle V caution |
