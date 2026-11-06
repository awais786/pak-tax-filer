# Research: Telemetry, Guardrails and PDF Export (008)

Each decision: what was chosen, why, and what else was considered.

## R1. Telemetry standard and exporter

- **Decision:** OpenTelemetry SDK with the FastAPI and SQLAlchemy instrumentations. Exporter
  chosen by the `OTEL_EXPORTER` setting: `console` (default, to the backend logs) or `otlp` (to
  Jaeger at `http://jaeger:4317`). Jaeger all-in-one runs under the Compose profile
  `telemetry`, so `docker compose up` doesn't start it until the lead approves.
- **Rationale:** the vendor-neutral industry standard (design approach A); switching viewers is a
  setting.
- **Alternatives:** own table and page; hosted LLM observability (design, rejected).

## R2. What is recorded, and what never is

- **Decision:** request spans named by **route template** (`GET /api/documents/{id}`), status and
  duration; SQLAlchemy spans with `enable_commenter=False` and statement text dropped by a span
  processor; no user or session id attributes; request/response bodies and headers never
  captured.
- **Rationale:** FR-010 and FR-012 (Principle V); the conservative choice from the design.

## R3. AI call spans

- **Decision:** one context manager `ai_call(feature, model)` in `app/telemetry/ai.py`, used by
  003's extraction client, 004's and 005's summaries, 006's answer and 007's agents. It sets the
  OpenTelemetry GenAI attributes `gen_ai.system="anthropic"`, `gen_ai.request.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, plus `app.feature`
  (`extraction`, `tax_summary`, `wealth_summary`, `assistant`, `workflow_document`,
  `workflow_validation`, `workflow_research`) and `app.outcome` (`passed`, `check_failed`,
  `timeout`, `fallback`).
- **Rationale:** one place to keep attributes consistent; GenAI attribute names are the
  standard's.
- **Alternatives:** an auto-instrumentation package for the Anthropic SDK (records prompts and
  replies by default, against FR-012).

## R4. Import rules

- **Decision:** `.importlinter` "forbidden" contracts: `app.tax.engine`, `app.tax.rates` and
  `app.wealth.reconcile` may not import `anthropic`, `app.documents.extraction`, `app.rag` or
  `app.workflow.agents`. Run by `lint-imports` in the guardrails job. 005's
  `test_reconcile_imports.py` stays and is listed in the suite README.
- **Rationale:** enforces Principle I by structure (design approach B).

## R5. Guardrail suite

- **Decision:** `backend/tests/guardrails/`, one file per principle, reusing the fake clients and
  fixtures of 003–007:
  - **I:** fake clients return made-up numbers; tax, wealth and workflow results equal the
    worked-example values.
  - **III:** a user with one confirmed and one `needs_review` certificate: the unconfirmed one is
    absent from `GET /api/tax`, `GET /api/wealth`, `calculate_income_tax` and the workflow gate;
    `GET /api/workflow/result` without approval → `409`.
  - **IV:** assistant answers in and out of corpus (cited / refused); every result endpoint
    returns the label; every PDF page carries the banner.
  A `guardrails` CI job runs `lint-imports` then `pytest tests/guardrails` on every PR and push.
  Screen label tests stay in the frontend job (README lists them).
- **Rationale:** FR-008, FR-009; no duplicated fixtures.

## R6. PDF rendering

- **Decision:** Jinja2 templates rendered to HTML, then `weasyprint.HTML(string=…).write_pdf()`.
  The banner is a CSS running header (`@page { @top-center { content: element(banner) } }`) so it
  repeats on every page. The backend image installs WeasyPrint's system packages (Pango,
  HarfBuzz).
- **Rationale:** design approach A; layout in HTML/CSS; banner on every page by construction.

## R7. Validation status

- **Decision:** `app/reports/status.py` builds the banner's status lines: tax (confirmed
  certificates + 003's rule warnings from `rules.py`, or "No warnings"), wealth (salary from
  certificates, other rows entered by the user + 005's provisional notes), workflow (plus
  `approved_at`). Uses existing functions only.
- **Rationale:** FR-003, FR-004; nothing new is calculated.

## R8. Endpoints and frontend

- **Decision:** `GET /api/tax/{tax_year}/pdf`, `GET /api/wealth/{tax_year}/pdf`,
  `GET /api/workflow/result/pdf` returning `application/pdf` with
  `Content-Disposition: attachment`; `409` with the reason when blocked, not ready or not
  approved. A `DownloadPdfButton` on the Tax, Wealth and Workflow result screens, disabled with the
  reason when the result can't be exported.
- **Rationale:** reuses each feature's existing protection and result functions.
