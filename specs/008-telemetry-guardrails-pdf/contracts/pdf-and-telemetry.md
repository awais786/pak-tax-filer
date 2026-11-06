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

- Setting `OTEL_EXPORTER`: `console` (default) or `otlp`; `OTEL_EXPORTER_OTLP_ENDPOINT` default
  `http://jaeger:4317`.
- `docker compose --profile telemetry up -d` starts Jaeger; its UI is at `http://localhost:16686`
  (pending the lead's approval).
- Span attributes per [data-model.md](../data-model.md).

## Guardrails CI job

Job `guardrails` in `.github/workflows/ci.yml`, on every pull request and push to `main`:
`lint-imports` (contracts in `.importlinter`), then `pytest tests/guardrails`. A failure blocks
merge (constitution, merge gates).

## Frontend

`DownloadPdfButton` on the Tax page, the Wealth page and the workflow's result step: downloads
the PDF; disabled with the reason when the endpoint would return `409`.
