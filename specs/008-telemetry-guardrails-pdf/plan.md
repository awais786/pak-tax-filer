# Implementation Plan: Telemetry, Guardrails and PDF Export

**Branch**: `008-telemetry-guardrails-pdf` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-telemetry-guardrails-pdf/spec.md`

## Summary

OpenTelemetry instruments FastAPI (route templates), the database (timings, no statement text;
our own listener, research R2) and
every Gemini call through one wrapper that adds GenAI attributes, the feature and the outcome;
spans go to the backend logs, for developers only (amended 2026-11-12: no viewer in 008; one can
be added later by a setting). A `guardrails` CI job runs
`import-linter` contracts and a cross-app pytest suite for Principles I, III and IV. PDFs are
HTML templates rendered by WeasyPrint with the banner as a repeated page header, served by three
`…/pdf` endpoints and read back with `pypdf` in tests. Decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 26 (as in 001's CI)

**Primary Dependencies**: added (libraries): `opentelemetry-sdk`,
`opentelemetry-instrumentation-fastapi`, `weasyprint`, `jinja2`; dev: `import-linter`. Existing: FastAPI, SQLAlchemy, `google-genai`
(003–007), `pypdf` (003). No new stack component (amended 2026-11-12: no Jaeger, no OTLP exporter).

**Storage**: none added (PDFs and telemetry are not stored in the database)

**Testing**: pytest with an in-memory span exporter and the fake AI clients from 003–007;
`pypdf` to read PDFs back; `lint-imports`; Vitest

**Target Platform**: local Docker Compose (from 001) and the 1 GB GCP VM: WeasyPrint measured at
+70 MB image, 71 MB peak memory per render (research R6)

**Project Type**: web application

**Performance Goals**: PDF within 5 seconds (SC-002); telemetry adds no noticeable delay
(batching exporter)

**Constraints**: no user content in telemetry (FR-012, Principle V); banner on every PDF page
(Principle IV); no AI text in PDFs (FR-005)

**Scale/Scope**: 3 PDF endpoints, 2 templates, 1 CI job, 1 telemetry wrapper at the 5 places
that call Gemini (8 AI uses: extraction, 2 summaries, answers, embeddings, 3 agents)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | PDFs hold only code-computed figures; import rules keep `google.genai`, the RAG code and the agents out of engine, rates, reconciliation (R4) |
| II. Authoritative sources | PASS | PDFs show 004's rule locations and 006's citations unchanged |
| III. Human confirmation | PASS | Guardrail suite covers every reader of certificates and the workflow gate (R5) |
| IV. Honest output | PASS | Banner on every page (R7), tested by reading PDFs back |
| V. Synthetic data only | PASS | Telemetry has no content, ids, raw paths or SQL text (R2) |
| VI. Test-first, measured AI | PASS | Guardrails written as tests first; AI outcomes measured in telemetry |
| VII. MVP scope | PASS | No analytics, alerting, hosted dashboards or stored PDFs (FR-014) |
| Stack | PASS | No new component (amended 2026-11-12: Jaeger dropped; logs only). Libraries follow 002's precedent (`pwdlib`) |
| Secrets | PASS | No new secrets |

**Post-design re-check:** PASS.

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
frontend/src/components/DownloadPdfButton.tsx (+ test), used in 007's TaxResultView (Tax page and
Guided filing's result) and the Wealth page
```

**Structure Decision**: telemetry and reports are their own packages so existing features only
change where they call Gemini (one wrapper) or add a button; guardrails live in one folder with
their own CI job.

## Complexity Tracking

No constitution violations; nothing to justify (amended 2026-11-12: the Jaeger service, the one
item here before, was dropped for logs only).
