# Data Model: Admin Area (011)

One migration (`0009_admin_area`): two columns on `users` and two new tables. Nothing else
changes; no figure, document or profile table gains a column.

## users (two new columns)

| Column | Type | Notes |
|---|---|---|
| is_admin | boolean | not null, default false. True only for staff accounts made by `create-admin` (FR-001); such accounts can't use the taxpayer app (FR-002). |
| disabled_at | timestamptz | null = active. Set by the disable action, cleared by re-enable (FR-014a/b). A disabled account is refused at sign-in, by `current_user` and by the token check. |

**State:** active (`disabled_at` null) → disabled (set) → active (cleared) …; deleting an account
removes the row (and every row that cascades from it).

## admin_audit_log

| Column | Type | Notes |
|---|---|---|
| id | uuid | primary key |
| admin_id | uuid | not null; the admin who acted. No foreign key: survives any account's deletion (FR-017). |
| action | varchar | not null; one of `view_account`, `disable`, `enable`, `delete_account`, `sign_out_everywhere`, `reset_reading_limit` |
| target_user_id | uuid | not null; the account acted on or viewed. No foreign key. |
| at | timestamptz | not null, default now() |

Index on `at` (the page lists newest first). Insert-only: no update or delete in code, no clean-up
(FR-017). No email, figure or document content (FR-016).

## telemetry_spans

| Column | Type | Notes |
|---|---|---|
| id | bigint | primary key, identity |
| kind | varchar | not null; `request` or `ai` |
| name | varchar | not null; the span's name (e.g. `GET /api/tax/{tax_year}`, `generate_content gemini-…`) |
| started_at | timestamptz | not null |
| duration_ms | double precision | not null |
| error | boolean | not null; the span's status was an error |
| route | varchar | null; `http.route` (a template, never with ids) |
| method | varchar | null; `http.request.method` |
| status_code | integer | null; `http.response.status_code` |
| feature | varchar | null; `app.feature` (`extraction`, `assistant`, `embeddings`) |
| model | varchar | null; `gen_ai.request.model` |
| operation | varchar | null; `gen_ai.operation.name` |
| outcome | varchar | null; `app.outcome` |
| input_tokens | integer | null; `gen_ai.usage.input_tokens` |
| output_tokens | integer | null; `gen_ai.usage.output_tokens` |

Index on `started_at`. Only the attributes in `app/telemetry/setup.py`'s `ALLOWED` reach these
columns (FR-019); database spans aren't saved. Rows older than 30 days are deleted (FR-021).

## Not stored

The admin session is a row in the existing `sessions` table (feature 002), distinguished only by
its cookie (`admin_session`, path `/admin`) and its 8-hour expiry. Dashboard counts, the account
overview, the Tax result and the telemetry page's figures are computed on each request and never
stored.
