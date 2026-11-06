# Data Model: Telemetry, Guardrails and PDF Export (008)

No database tables are added. PDFs and telemetry are not stored in the database.

## Telemetry span attributes

| Span | Attributes |
|---|---|
| Request | `http.request.method`, `http.route` (template, no ids), `http.response.status_code`, duration |
| Database | duration only (statement text dropped) |
| AI call | `gen_ai.system` = `anthropic`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `app.feature`, `app.outcome`, duration |

`app.feature`: `extraction`, `tax_summary`, `wealth_summary`, `assistant`, `workflow_document`,
`workflow_validation`, `workflow_research`. `app.outcome`: `passed`, `check_failed`, `timeout`,
`fallback`.

**Never present:** prompts, replies, document contents, figures, emails, user or session ids, raw
paths with ids, SQL text, request or response bodies, headers, cookies (FR-012).

## PDF content (generated, not stored)

| PDF | Body | Banner (every page) |
|---|---|---|
| Tax | 004's figures, breakdown with rule locations, separate balances | label + "Demo data only." + "All figures are from your confirmed certificates" + 003's warnings or "No warnings" + generated date and tax year |
| Workflow | as Tax, plus 007's cited passages | as Tax + "Approved by you on [date]" |
| Wealth | 005's rows, reconciliation, result in words | label + "Demo data only." + "Salary figures are from your confirmed certificates; other rows were entered by you" + 005's provisional notes or "No warnings" + date and tax year |

Label text, unchanged from 004/005/006: "Not yet reviewed by a tax practitioner. Not tax advice."
No AI-written text appears in any PDF (FR-005).
