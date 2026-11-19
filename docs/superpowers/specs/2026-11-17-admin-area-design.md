# Admin area (design)

**Date:** 2026-11-17 · **Feature:** 011 (next free number; 009 is paused, 010 merged)
**Asked by:** Awais ("https://fastapi-admin-docs.long2ice.io/ — try to integrate it also"), shaped
with Saifullah through brainstorming on 2026-11-17.

## Why

Every app like this has an internal back office for the people who run it. PakTaxFiler has none:
there is no admin role, no way to see how the app is used without reading the database, and
telemetry (feature 008) only goes to the backend log and is lost. Awais asked for an admin panel
built with a library. Saifullah asked for what is normal for this kind of application, and chose
from options at each step.

## Goals

- One internal admin area at `/admin` for the people running the app.
- Admins can see the app's state (accounts and their progress, documents, results, guided runs,
  AI use, the law library, telemetry) and take four account actions.
- Every admin action, and every time an admin opens one person's details, is recorded in an
  audit log.
- Telemetry is saved (no content) for 30 days and shown on a telemetry page.

## Non-goals

- Not for customers, and not a tax-practitioner review tool (that would be a separate,
  customer-facing feature, as in other tax products). Saifullah: "I wouldn't like it to serve two
  kinds of people."
- No editing of records: no changing figures, confirming documents or editing profiles.
- No roles beyond one admin role (Saifullah: "A for now").
- No external monitoring service (Grafana, Sentry); no Redis.
- No downloading users' uploaded files from the admin area (my call: the files are the most
  personal data in the app, and nothing in the goals needs them).

## Anti-goals (a failure even if it works)

- Any admin path that changes a user's tax figures or confirms a document for them (constitution
  Principle III: only the user confirms).
- Showing a password, session token or access token, even as a hash.
- Saving content in telemetry or the audit log (prompts, replies, figures, emails, document text),
  which feature 008 forbids for telemetry.
- An admin action that bypasses the app's own code, e.g. deleting a user row and leaving their
  uploaded files behind.

## Decisions (Saifullah's, from the options offered)

| Decision | Chosen |
|---|---|
| Who it's for | One internal admin area for the team (the industry norm) |
| How much admins can do | View everything except secrets, plus four actions (option B): disable / re-enable an account, delete an account, sign a user out everywhere, reset a user's daily AI limit |
| Telemetry | Save it in our own database, no content, keep 30 days, show a telemetry page (option A) |
| Roles | One admin role, for now (option A) |
| Audit log | Every action plus every opening of one person's details (option A) |
| How it's built | starlette-admin mounted in the FastAPI backend (option A) |

## Approaches considered (how to build)

| | Approach | Trade-off | Outcome |
|---|---|---|---|
| A | starlette-admin (MIT; 1.0.3, Oct 2026; Python 3.13; SQLAlchemy 2 `AsyncEngine`; built-in stat/chart widgets; per-view `can_create/can_edit/can_delete`; custom actions; `AuthProvider`) mounted at `/admin` | Server-rendered pages in the library's theme, not our app's look; needs `/admin` routed to the backend | **Chosen**: what Awais asked for in spirit (a library), fits our stack, least code |
| B | SQLAdmin, same way | Similar; couldn't confirm its latest version or Python 3.13 support; weaker dashboard support | Not chosen |
| C | Our own React pages + `/api/admin` endpoints | Matches the app's look; several times the code for an internal tool | Not chosen |
| — | fastapi-admin (what Awais linked) | Requires Tortoise ORM and Redis; last release June 2022, Python ≤ 3.10 | Ruled out: doesn't fit SQLAlchemy 2.1 / Python 3.13 |

## Constraints

- Constitution 1.3.0: Principle VII (MVP scope) needs a dated MINOR amendment adding the admin
  area before any code (as feature 010 did). Principles I–VI apply unchanged: no AI anywhere in
  this feature; synthetic data only.
- Stack: FastAPI, async SQLAlchemy 2.1, Alembic, Postgres; Python 3.13. New dependency:
  `starlette-admin` only (it brings Jinja2, python-multipart, itsdangerous).
- Server: one GCP e2-micro with 1 GB of memory. Telemetry storage must stay small.
- Routing: Caddy (`deploy/Caddyfile`) sends only `/api/*` to the backend today, Vite
  (`frontend/vite.config.ts`) proxies only `/api`. Both need `/admin` (and its static assets)
  sent to the backend.
- Security headers in Caddy (`X-Frame-Options: DENY`, `nosniff`, HSTS) stay.
- Follow the repo's rules: Spec Kit chain (specify → clarify → plan → tasks → analyze), TDD,
  contracts updated with every endpoint/table change, `docs/api-conventions.md` where it applies.
- Ships in one pull request together with the 004 bank-profit fix, as Saifullah asked: the
  feature branch `011-admin-area` stacks on `fix/004-bank-profit-final-tax`, and its PR contains
  both. The PR asks Awais (who reviews spec and plan before merge, per the constitution) to accept
  starlette-admin in place of fastapi-admin and the Principle VII amendment.
- The admin contract is a Markdown page contract (`contracts/admin-pages.md`), not `*-api.md`:
  the admin pages are a mounted sub-app outside the API schema, so the contract check doesn't
  expect them in an `api.yaml`. The new tables go in `data-model.md`, which the check verifies.

## How it works (decided)

### Admins and login
- Admin accounts are **staff-only** (my call after the builder check; the norm keeps staff and
  customer accounts apart): an admin can't use the taxpayer app or MCP. The app's login,
  `current_user` and the MCP token check (`owner_of`) refuse an admin account with the same answer
  as a wrong password or no session.
- An admin account is created only from the command line, never through a web page:
  `python -m app.cli create-admin --email …` (prompts for the password twice, like `create-user`).
  It creates a **new** account and refuses an email that already exists: it never promotes a
  taxpayer account. An admin account has no profile, documents or guided run.
- Storage: an `is_admin` flag on `users` (one account table and one password scheme rather than a
  second account system), plus `disabled_at` (null = active) for the disable action.
- `/admin` has its own login page (starlette-admin's). Only active admin accounts get in; a
  taxpayer account, a wrong password and a disabled account all get the same generic refusal.
  Failures are throttled like the app's login (feature 002's `throttle`), counted under a separate
  key (`" admin:"` + email; a leading space, which the public login can't produce) so failures on the public login can't lock an admin out of `/admin`.
- Session: the app's own `sessions` table (hashed tokens, `create_session`), with a separate
  `admin_session` cookie: `HttpOnly`, `Secure` unless `COOKIE_SECURE=false`, `SameSite=Strict`,
  path `/admin`, and a shorter lifetime than the app's 7 days (8 hours, my call: the norm for admin
  consoles). Because admin accounts can't use the app, an admin session token is useless as an app
  cookie and vice versa. No new secret is needed unless starlette-admin itself requires one, in
  which case it comes from the environment (never code or a file).
- Admin pages never change a user's data just by being viewed: in particular the guided run is read
  as stored, never through `workflow.service.get_run` (which re-runs the steps and saves).

### What admins see
- **Dashboard** (stat widgets): taxpayer accounts; profiles set up; documents uploaded, confirmed
  and failed; guided runs per step; extraction attempts in the last 24 hours against the limits
  (10 per user, 100 app-wide); Ask questions in the last 24 hours against the app's cap (200) and
  the busiest user's last hour against the per-user limit (30 an hour).
- **Accounts**: list with search by email; columns email, created, admin?, disabled?. An account's
  detail shows its tax year and ATL status, its documents and their status, its Tax result (004's
  engine on its confirmed documents, as the Tax page computes it: figures or the refusal reason)
  and its guided run's step. Opening an account's detail writes a `view_account` audit entry.
- **Documents**: list (type, status, tax year, created, owner's email); no file download.
- **Law library**: the corpus documents with passage counts.
- **Telemetry**: see below.
- **Audit log**: list, newest first, read-only for everyone.
- Never shown anywhere: `password_hash`, sessions and their token hashes, personal access tokens
  and their hashes, question text (not stored anyway).
- Every view is read-only (`can_create`, `can_edit`, `can_delete` off), except the four actions.

### The four actions (each one audit-logged)
| Action | Effect |
|---|---|
| Disable | Sets `disabled_at`, deletes the user's sessions and personal access tokens. The app's login, `current_user` and the MCP token check refuse a disabled user (same generic refusal as a wrong password). |
| Re-enable | Clears `disabled_at`. The user signs in again normally. |
| Delete account | **Files first** (my call after the builder check): remove every stored file of the account's documents through the storage layer (local or bucket), and only then delete the documents and the user row in one transaction (everything else cascades). If storage can't be reached, the deletion stops with a clear message and no rows are deleted; a retry is safe (removing a file that's already gone is fine). This order is the only one that can't leave files behind. Confirmation step required. |
| Sign out everywhere | Deletes the user's sessions (not their access tokens). |
| Reset daily AI limit | Deletes the user's extraction attempts from the last 24 hours, so they can extract again. This also frees the same number of app-wide attempts (my call: simplest, and logged). |

Actions live in plain service functions (testable without the admin UI); the admin views only
call them. The four actions apply to taxpayer accounts only, never to an admin account (admins are
managed from the command line), so no admin can lock the others out.

### Audit log
- Table `admin_audit_log`: id, admin user id, action (`view_account`, `disable`, `enable`,
  `delete_account`, `sign_out_everywhere`, `reset_reading_limit`), target user id, at. No foreign key
  on either user id, so entries survive any account's deletion; no email, figures or other
  content. The page shows the emails of accounts that still exist, else the ID.
- Insert only: no update or delete path in code; never cleaned up automatically.

### Telemetry storage
- A span exporter (added beside the console one, after the existing `ALLOWED` filter) writes
  finished spans to a `telemetry_spans` table: name, kind, start time, duration, status, and only
  the `ALLOWED` attributes (route, method, status code, AI feature, model, outcome, tokens).
- Saved: HTTP request spans and AI-call spans only. Not saved: database spans (volume), and the
  exporter's own inserts must not create spans (no feedback loop).
- Written in batches, off the request path; a failure to write never fails a request. The
  exporter runs in OpenTelemetry's background thread while our database code is async, so it only
  queues rows in memory (bounded: drops the oldest if full); a background task started with the
  app writes the queue in batches with the async engine, without creating database spans of its own
  (production runs one backend process, so one writer).
- Rows older than 30 days are deleted automatically (when: builder's call, e.g. with each batch or
  once a day).
- `OTEL_EXPORTER` keeps working for the log output; saving to the database is on by default in
  dev and production, off in tests unless a test turns it on.
- Telemetry page: requests per day, error rate (5xx share), slowest routes (median and 95th
  percentile), AI calls per feature by outcome, AI call duration, tokens per day.

## Left to the builder

- Exact starlette-admin wiring (mounting, templates, widgets, action buttons), after a short spike
  to confirm its `AuthProvider`, actions and async support work as documented.
- Session mechanism details within the rules above.
- Table and column names beyond those named here; migration numbering.
- When the 30-day telemetry clean-up runs.
- The command name for creating an admin.
- Page layout and labels.
- Tests: test first for every rule above, including that each view refuses create/edit/delete, that
  secrets never appear in any admin page, that a non-admin can't log in, that disabled users are
  refused everywhere, that delete removes stored files, that each action and each detail view
  writes exactly one audit entry, and that saved telemetry holds only `ALLOWED` attributes. An e2e
  test logs in as an admin and disables an account.
