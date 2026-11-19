# Research: Admin Area (011)

Source design: `docs/superpowers/specs/2026-11-17-admin-area-design.md`. Every decision below was
checked against the installed library in a throwaway run (`uv run --with starlette-admin`, nothing
added to the project) on 2026-11-17.

## R1. The admin library

**Decision:** `starlette-admin` 1.0.3 (MIT), mounted in the FastAPI app with `Admin.mount_to(app)`
at `base_url="/admin"`, using `starlette_admin.contrib.sqla.Admin` with the app's own
`async_sessionmaker`.

**Checked in the spike:** it resolves with the backend's exact versions (starlette 1.10.0, FastAPI
0.162.0, SQLAlchemy 2.1.8, Jinja2 3.1.6); `Admin(session_provider=...)` accepts an
`async_sessionmaker`; `ModelView` has per-request `can_create`, `can_edit`, `can_delete`,
`can_export`, `can_import`, `can_view_detail`; `row_action(name, text, confirmation=...)` and
`is_row_action_allowed_for_obj` give per-row actions with a confirmation step; `CustomView`,
`StatWidget`, `ChartWidget` and `TableWidget` take async callbacks for the dashboard and the
telemetry page; static assets ship in the package.

**Alternatives:** fastapi-admin (what the lead linked: needs Tortoise ORM and Redis, last release
June 2022, Python ≤ 3.10); SQLAdmin (similar, but its Python 3.13 support and latest release
couldn't be confirmed, and its dashboard support is weaker); our own React pages (several times
the code). Recorded in the plan as a new dependency (constitution, Technology section).

## R2. Admin sign-in and session

**Decision:** a custom `AuthProvider`:
- `login(username, password, remember_me, request)`: one attempt at a time per key, refuse if
  throttled, check the password with the app's existing password check, and admit only an account
  with `is_admin` and no `disabled_at`; any failure records a throttle failure under the key
  `" admin:"` + email (a leading space the public login can't produce: review M3; over-long input refused first: review M2) and raises `LoginFailed` with one generic message. On success it creates a row in
  the app's `sessions` table (`sessions.create_session`, given an 8-hour lifetime) and returns a
  redirect to the admin index that sets the `admin_session` cookie: `HttpOnly`,
  `Secure` unless `COOKIE_SECURE=false`, `SameSite=Strict`, `Path=/admin`, max age 8 hours.
- `authenticate(request)`: read `admin_session`, look up the session (`get_user_for_token`), and
  return an `AdminUser` only for an active admin; otherwise `None` (the library sends them to the
  login page).
- `logout(request)`: delete the session and clear the cookie.

The library's own `request.session` (cookie sessions) is not used.

**Rationale:** reuses the hashed-token sessions already reviewed in feature 002; the session can be
ended by deleting its row; no second session system.

## R3. The library's CSRF and flash cookies

**Decision:** `Admin(secret_key=...)` from a new optional setting `ADMIN_SECRET_KEY` (kept out of
`repr`). When unset, the library generates a random key at start-up (its documented fallback) and
warns once itself, without the key (amended in T013: our own warning was a duplicate).

**Rationale:** the library signs its CSRF token and flash messages with this key. One backend
process runs in production, so a start-up key works; it only means admin forms open across a
restart must be reloaded. Setting the variable on the server avoids that, and it needs no file.

## R4. Staff-only admin accounts

**Decision:** `users.is_admin` (default false) and `users.disabled_at` (null = active). The app's
login, `current_user` and the MCP token check (`tokens.service.owner_of`) refuse an admin or a
disabled account with their existing generic answers. The admin provider uses
`get_user_for_token` directly and applies its own rule (admins only). `create-admin` in
`app/cli.py` creates a new admin account and refuses an existing email.

**Rationale:** the norm keeps staff and customer accounts apart; it also makes an admin session
token useless as an app cookie and vice versa, closing the gap a shared `sessions` table would
otherwise open (builder check).

## R5. Read-only views and no secrets

**Decision:** every `ModelView` returns false from `can_create`, `can_edit`, `can_delete`,
`can_export` and `can_import`, and lists its `fields` explicitly. Views: accounts (email, created,
admin, disabled), documents (type, status, tax year, created, owner email; no file, no detail page),
law library (corpus documents with passage counts), audit log. Never registered as views:
`sessions`, `personal_access_tokens`, `login_failures`, `ask_requests`, `extracted_fields`,
`extraction_attempts`. A test opens every admin page as an admin and checks no password hash,
session token hash or access-token hash appears.

## R6. The account page and its audit entry

**Decision:** the accounts view's detail page adds an overview built by a plain service function
`account_overview(db, user)`: profile (tax year, ATL), documents with status, the Tax result from
004 (`tax_inputs` + `calculate`, as the Tax page computes it: figures or refusal reason), and the
guided run's step read straight from `workflow_runs` (never `workflow.service.get_run`, which
re-runs and saves). The view overrides its record lookup: when
`request.state.action == RequestAction.DETAIL` it writes one `view_account` audit entry (the
library sets that state only on the detail page, so list pages and actions don't).

## R7. The four actions

**Decision:** plain async service functions in `app/admin/actions.py`, each taking the admin and the
target, refusing an admin target, doing its work and writing its audit entry in one transaction:

| Function | Work |
|---|---|
| `disable_account` | set `disabled_at`, delete sessions and personal access tokens |
| `enable_account` | clear `disabled_at` |
| `delete_account` | collect every document's `file_path`; delete each through `storage.delete`; any `StorageUnavailable` stops before any row changes (the admin sees "Storage can't be reached; nothing was deleted, try again later"); then delete the user (cascades) and write the entry; a target already gone says so and writes nothing |
| `sign_out_everywhere` | delete sessions |
| `reset_reading_limit` | delete the user's `extraction_attempts` in the last 24 hours (`DAILY_WINDOW`) |

The accounts view exposes them as `row_action`s with confirmations; `is_row_action_allowed_for_obj`
hides all four on admin accounts and shows disable or re-enable by state.

## R8. Audit log

**Decision:** table `admin_audit_log` (see data-model.md), insert-only: the only code path is
`record(db, admin_id, action, target_id)`; the view is read-only. No foreign keys, so entries
outlive any account. The page joins emails of accounts that still exist.

## R9. Saving telemetry

**Decision:** a `DatabaseSpanExporter`, added through the existing `add_exporter` (so it only ever
sees spans after the `ALLOWED` filter), keeps request spans (server kind) and AI-call spans (those
with `gen_ai.operation.name`) and puts one plain row per span on a bounded in-memory queue
(`collections.deque(maxlen=10_000)`, drops the oldest; safe across OpenTelemetry's export thread).
A writer task started in the app's lifespan inserts the queue every 5 seconds using the app's
engine with OpenTelemetry instrumentation suppressed (our `instrument_engine` listener learns to
skip spans while suppression is on, so the writer's own inserts create no spans), and once an hour
deletes rows older than 30 days. Any error in the writer is logged without content and dropped;
requests never wait for it. Setting `TELEMETRY_STORE` (`on`/`off`, default `on`); tests set it
`off` like `OTEL_EXPORTER=none`, and turn it on in their own fixture.

**Rationale:** the exporter thread can't use the async session; a queue plus one writer keeps
inserts off the request path; production runs one process.

**Found in T027:** each write is shielded from cancellation and the writer flushes the queue when
the app stops, so stopping mid-write loses nothing; the clean-up runs on the first beat and then
about hourly. Checked live in development: request rows saved with route templates only.

## R10. The telemetry page

**Decision:** a `CustomView` at `/admin/telemetry` whose widgets read `telemetry_spans` for the last
30 days: requests per day, server-error share (5xx), slowest routes (median and 95th percentile,
Postgres `percentile_cont`), AI calls per feature by outcome, AI call duration, tokens per day.

## R11. Routing

**Decision:** Caddy gets `handle /admin /admin/* { reverse_proxy backend:8000 }` before the static
handler; Vite's dev proxy gets `"/admin": "http://backend:8000"`. Existing security headers stay.

## R12. Third-party requests

**Decision (done in T021):** the library's `base.html` imported the Inter font from `rsms.me`.
A local `app/admin/templates/base.html` extends the library's own copy (loaded under the
`starlette_admin/` prefix by a `PrefixLoader`) and replaces only its `fonts` block with the system
font stack. A test checks no admin page loads anything from another site.

## R13. Logging

**Decision:** set the `starlette_admin` logger to `CRITICAL` (amended during T013, from WARNING):
at `INFO` and `WARNING` the installed version logs the typed login email (`username=...`) on every
sign-in, and each detail page's record id; personal data never reaches our logs.

**Also found in T013:** the library's logout accepts POST only (with the CSRF token, field
`csrftoken`); its own CSRF cookie is `SameSite=Lax` (a double-submit token, not a login; the
`admin_session` cookie stays Strict); its login form labels the field "Username" inside a block
that also holds the password field, so relabelling it would mean copying the whole page (not
done, recorded as a ruling); "Remember me" is shown but ignored (admin sessions are always 8 hours).
The admin is mounted with a session factory built on first use (`AppSessions`), so importing the
app still needs no `DATABASE_URL`.

## R14. Keeping AI out

**Decision (amended in T030):** a new import-linter contract for `app.admin` that forbids
**direct** imports of `google`, `app.documents.extraction`, `app.rag.answer` and `app.rag.embed`
(`allow_indirect_imports = True`), plus a guardrail test: with Google's client made to fail on
creation, every admin page and all four actions still work (FR-024). `app.rag.service` isn't
banned: the dashboard takes the Ask page's hourly limit from it, and it calls no model itself.
Faking the app's AI dependencies wouldn't prove anything here, since the admin area takes none.

**Why not the existing contract:** the admin area reads confirmed documents through
`app.documents.service.confirmed_documents` (the only sanctioned path, Principle III), and that
module imports the extraction client; so an indirect-import ban can't hold. The law-library view
reads `app.rag.models` only.
