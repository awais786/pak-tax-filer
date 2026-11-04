# Contract: Workflow API, agent tools and page

Base path `/api/workflow`. All endpoints need `current_user` and 002's `require_profile`
(`401` / `409` "Set up your profile first."). Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md).

## Run object

```json
{ "step": "gate", "tax_year": "2025-26", "fingerprint": "…",
  "document": { "message": "…", "missing": [] },
  "validation": { "message": "…", "issues": [] },
  "research": { "note": "…", "passages": [{ "source": "Income Tax Ordinance 2001", "location": "§149(1)", "page": 12, "text": "…" }] },
  "gate": { "figures": { "taxable_salary": "1800000.00", "tax_deducted": "75000.00", "gross_profit": "0.00", "tax_withheld": "0.00" }, "on_atl": true },
  "approved_at": null, "done_at": null }
```

Step texts carry `"fallback": true` when the code-written result was used.

## Endpoints

| Endpoint | Does | Success | Errors |
|---|---|---|---|
| `GET /api/workflow` | Current run; re-runs steps 1–3 first if inputs changed | `200` run, or `404` none started | — |
| `POST /api/workflow/start` | Start or restart; runs steps 1–3 | `200` run | — |
| `POST /api/workflow/approve` | Record approval at the gate | `200` run (`step: "result"`) | `409` not at the gate, or inputs changed since the run was shown |
| `POST /api/workflow/back` | Leave the gate | `200` run (`step: "document"`) | `409` not at the gate |
| `GET /api/workflow/result` | 004's tax result (same body as `GET /api/tax/{tax_year}`) plus `passages` | `200` | `409` "Approval needed." when not approved for the current inputs |
| `POST /api/workflow/done` | Mark done | `200` run (`step: "done"`) | `409` not at the result step |

The run's `fingerprint` is its `outputs_fingerprint` (added 2026-11-04: `approve` needs it).
`approve` sends the `fingerprint` the user saw (`{"fingerprint": "…"}`); a mismatch means the
inputs changed and returns `409`.

## Agent tools (read-only, `app/workflow/tools.py`)

| Agent | Tool | Returns |
|---|---|---|
| Document | `list_confirmed_documents()` | type, label, confirmed time per confirmed certificate; upload page links |
| Validation | `validate_salary_information(tax_year, gross_salary, taxable_salary, tax_deducted)` | 006's MCP output: `ok`, `issues` |
| Validation | `check_bank_certificate(tax_year, profit_amount, tax_withheld)` | same shape, 003's bank rules |
| Research | `search_tax_documents(query)` | 006's search: passages with source, location, page |

No tool writes, confirms, approves or calculates (FR-010).

## Page

`/workflow` (under `RequireAuth` and `RequireProfile`), linked from the home page: a step
indicator; each step's message (links to 003's pages when something is missing); the gate with
figures, tax year, ATL status, issues, passages, **Approve** and **Go back**; the result with
004's breakdown, the passages as "Where this comes from", the practitioner label, and **Mark
done**.
