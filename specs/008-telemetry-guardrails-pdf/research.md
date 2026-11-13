# Research: Telemetry, Guardrails and PDF Export (008)

Each decision: what was chosen, why, and what else was considered.

## R1. Telemetry standard and exporter

- **Decision** (amended 2026-11-12): OpenTelemetry SDK with the FastAPI instrumentation and
  database spans of our own (R2), spans printed to the backend logs by the SDK's console exporter (batched).
  The `OTEL_EXPORTER` setting is `console` (default) or `none` (tests, or to silence it); no OTLP
  exporter and no viewer in 008. Telemetry is for developers only; there is no page in the app.
- **Rationale:** the vendor-neutral industry standard (design approach A), with nothing new in
  the stack. A viewer such as Jaeger can be added later with the OTLP exporter package and a
  setting, no code changes.
- **Alternatives:** logs plus an opt-in local Jaeger (a new component needing the lead's
  approval; measured at about 13 MB idle, so weight wasn't the reason); own table and page;
  hosted LLM observability (design, rejected).

## R2. What is recorded, and what never is

- **Decision:** request spans named by **route template** (`GET /api/documents/{id}`), status and
  duration; database spans with the duration only; no user or session id attributes;
  request/response bodies and headers never captured. Every exporter receives spans through one
  filter that keeps only the attributes listed in data-model.md and drops events and status
  descriptions, so content an instrumentation adds can't reach the logs.
- **Amended 2026-11-12 (implementation):** `opentelemetry-instrumentation-sqlalchemy` (0.66b2)
  supports SQLAlchemy below 2.1 only and silently records nothing with our 2.1.8. Database spans
  come instead from a few lines of our own on SQLAlchemy's cursor events
  (`app/telemetry/setup.py`, `instrument_engine`): a span per statement named by its first word
  (`SELECT`, `INSERT`, ...), with the duration and `db.system.name`, never the statement or its
  parameters. The package was removed.
- **Rationale:** FR-010 and FR-012 (Principle V); the conservative choice from the design.

## R3. AI call spans

- **Decision** (amended 2026-11-12): one context manager `ai_call(feature, model, operation)` in
  `app/telemetry/ai.py`, used at the five places that call Gemini: 003's extraction client,
  004's summary client (also 005's), 006's answerer and embedder, and 007's agent client. It sets
  OpenTelemetry's GenAI attributes as currently named: `gen_ai.provider.name="gcp.gemini"` (the
  AI Studio endpoint), `gen_ai.operation.name` (`generate_content`, `embeddings`, or
  `execute_tool` for an agent's tool call), `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`, plus `app.feature` (`extraction`, `tax_summary`,
  `wealth_summary`, `assistant`, `embeddings`, `workflow_document`, `workflow_validation`,
  `workflow_research`) and `app.outcome` (`passed`, `check_failed`, `timeout`, `fallback`,
  `limit_reached`).
- **Amended 2026-11-12 (implementation):** the span is opened where the app decides how the use
  ended, around the call and the checks on its answer (`verified_summary`, the wealth summary,
  the assistant's answer step, search and the corpus build for embeddings, document extraction,
  and each guided-run step), and `record_refusal` records a use a limit stopped before any call.
  So the outcome is known, and the spans appear with the fake clients too. The real Gemini clients
  add their token counts to that span (`record_gemini_usage`; extraction already reports its
  counts); Gemini's embeddings API returns none. Tool calls are child spans from `tool_call`.
- **Rationale:** one place to keep attributes consistent; the GenAI conventions are still
  "Development" and recently moved to their own repository, so their names live only in this
  module.
- **Alternatives:** an auto-instrumentation package for the Gemini SDK (may record prompts and
  replies, against FR-012); the older `gen_ai.system` name (superseded).

## R4. Import rules

- **Decision:** `.importlinter` "forbidden" contracts: `app.tax.engine`, `app.tax.rates` and
  `app.wealth.reconcile` may not import `google.genai`, `app.documents.extraction`, `app.rag`,
  `app.workflow.agents` or `app.workflow.client` (amended 2026-11-12: was `anthropic`; import-linter
  can only forbid an outside package whole, so the rule names `google`).
  Run by `lint-imports` in the guardrails job. 005's
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
