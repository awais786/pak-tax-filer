# Contract: PDF endpoints, telemetry and the guardrails job

Follows the [API conventions](../../001-repo-foundations/contracts/api-conventions.md). Each PDF
endpoint has the same protection as the result it exports (`current_user`, 002's
`require_profile`) and only ever returns the caller's own data.

## PDF endpoints

| Endpoint | Exports | Success | Errors |
|---|---|---|---|
| `GET /api/tax/{tax_year}/pdf` | 004's result | `200` `application/pdf`, `Content-Disposition: attachment; filename="tax-2025-26.pdf"` | `409` `{"detail": "<blocked reason message>"}` when 004 returns a `blocked_reason` |
| `GET /api/wealth/{tax_year}/pdf` | 005's statement and result | `200` PDF, `wealth-2025-26.pdf` | `409` with 005's not-ready reason |
| `GET /api/workflow/result/pdf` | 007's result | `200` PDF, `tax-2025-26.pdf` with the approval line | `409` "Approval needed." when not approved for the current inputs |

Content and banner per [data-model.md](../data-model.md). Generated per request; nothing stored.

## Telemetry

- Setting `OTEL_EXPORTER`: `console` (default, spans in the backend logs) or `none` (amended
  2026-11-12: no viewer in 008; telemetry is for developers only, with no page in the app).
- Span attributes per [data-model.md](../data-model.md).

## Guardrails CI job

Job `guardrails` in `.github/workflows/ci.yml`, on every pull request and push to `main`:
`lint-imports` (contracts in `.importlinter`), then `pytest tests/guardrails`. A failure blocks
merge (constitution, merge gates).

## Frontend

`DownloadPdfButton` on the Tax page, the Wealth page and the workflow's result step: fetches the
PDF through the API helper (`apiDownload`) and saves it under the server's file name; disabled with
the reason when the endpoint would return `409` (on the Wealth page also while there are unsaved
changes, since the PDF is of the saved statement); an error that arrives anyway (e.g. `409` after
a change in another tab, `401`) is shown on the page, never as a broken download (review
2026-11-12).
