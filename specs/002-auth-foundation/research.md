# Research: Authentication Foundation (002)

Each decision: what was chosen, why, and what else was considered.

## R1. Password hashing

- **Decision:** `pwdlib` with the Argon2 hasher.
- **Rationale:** Argon2 is the current recommended password hash (OWASP). `pwdlib` is what
  FastAPI's own security tutorial now uses; it is small and maintained.
- **Alternatives:** `passlib` (unmaintained, breaks on newer Python); bcrypt (fine, but older and
  limited to 72-byte passwords); writing our own on `argon2-cffi` (more code for no gain).

## R2. Session tokens and cookie

- **Decision:** at login, generate a random token (`secrets.token_urlsafe(32)`); store only its
  SHA-256 hash in the `sessions` table; send the token in a cookie named `session` with
  `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` of 7 days, and `Secure` on by default (a
  setting turns it off only for local development over plain HTTP).
- **Rationale:** an opaque token reveals nothing; hashing it means a leaked database can't be
  used to log in; `HttpOnly` keeps scripts from reading it.
- **Alternatives:** signed cookie holding the user ID (can't be revoked on logout); storing the
  raw token (a database leak would expose live sessions).

## R3. Cross-site request forgery (CSRF)

- **Decision:** rely on `SameSite=Lax` plus requiring `Content-Type: application/json` on all
  state-changing requests (login, logout). No CSRF token in this feature.
- **Rationale:** `Lax` stops the cookie being sent on cross-site POSTs, and a cross-site page
  can't send a JSON body without a CORS preflight that our backend won't approve. This is the
  standard defence for a same-origin JSON API.
- **Alternatives:** CSRF tokens (extra moving parts with no added protection here).

## R4. Login throttling

- **Decision:** a `login_failures` table records each failed attempt (normalized email,
  timestamp). Before checking a password, count failures for that email in the last 15 minutes;
  if 10 or more, refuse with `429` and a generic "try again later" message. Unknown emails are
  counted the same way.
- **Rationale:** survives restarts and works across several backend processes; simple to test.
  Treating unknown emails the same avoids revealing which emails exist.
- **Concurrency (added 2026-11-05, code review):** each login takes a per-email PostgreSQL
  advisory lock (`pg_advisory_xact_lock`) for its transaction, so simultaneous attempts are
  counted one at a time and can't all slip under the limit.
- **Accepted MVP limits (code review):** throttling is per email, not per IP (FR-007 asks for
  per email), so one client can try a password across many emails; `login_failures` rows are
  never deleted (harmless at demo scale; a cleanup can come with real traffic).
- **Alternatives:** in-memory counter (lost on restart, per-process); Redis (a new stack
  component for one counter).

## R5. Equal treatment of unknown emails

- **Decision:** when the email is unknown, still run a password verification against a fixed
  dummy hash, then return the same `401` message as for a wrong password.
- **Rationale:** without this, unknown emails answer faster, which leaks which emails exist.

## R6. Session expiry

- **Decision:** absolute expiry 7 days after login, stored as `expires_at` and checked on every
  request. Expired sessions are deleted when next used; no background cleanup job yet.
- **Alternatives:** sliding expiry (spec says 7 days after login); a cleanup scheduler (not
  needed at demo scale).

## R7. Creating demo users

- **Decision:** `python -m app.cli create-user --email <email>`, prompting for the password
  (hidden input), using standard-library `argparse` and `getpass`.
- **Rationale:** passwords never land in shell history; no new dependency.
- **Alternatives:** Typer/Click (an extra dependency for one command); password as an argument
  (ends up in shell history).

## R8. API layout and errors

- **Decision:** auth endpoints under `/api/auth/` (`login`, `logout`, `me`). Errors use
  FastAPI's default shape `{"detail": "<message>"}`. Vite's dev server proxies `/api` to the
  backend, so the browser sees one origin.
- **Rationale:** a single `/api` prefix keeps the proxy rule simple and is the start of the
  API conventions requested in issue #4.

## R9. Frontend routing and auth state

- **Decision:** React Router for pages; an auth context that calls `GET /api/auth/me` on load;
  a `RequireAuth` wrapper that sends logged-out users to `/login?next=<page>`; one fetch helper
  that sends the user to `/login` whenever an API call returns `401`.
- **Alternatives:** storing "logged in" in local storage (gets out of sync with the real
  session); a larger state library (unneeded for one piece of state).

## R10. Testing against the database

- **Decision:** backend tests use a separate `pak_tax_filer_test` database in the same Postgres
  container, migrated once per test run, with each test inside a rolled-back transaction.
- **Rationale:** tests hit real PostgreSQL behaviour (unique indexes, timestamps) without
  touching development data.
- **Alternatives:** SQLite for tests (behaves differently from PostgreSQL); mocking the
  database (misses real constraint behaviour).

## R11. Taxpayer profile storage and saving (added 2026-11-04)

- **Decision:** a separate `taxpayer_profiles` table with `user_id` unique (approach A in the
  design addendum). `PUT /api/profile` creates or replaces it with one
  `INSERT … ON CONFLICT (user_id) DO UPDATE`.
- **Rationale:** keeps `users` login-only; the unique key enforces one profile per user (FR-016)
  in the database; the upsert settles two saves arriving together (last one wins, one row).
- **Alternatives:** columns on `users`; separate create and edit endpoints (two code paths for
  two fields); read-then-write in code (races).

## R12. FBR ATL check link

- **Decision:** link to FBR's "Check Active Taxpayer Status" page,
  `https://www.fbr.gov.pk/categ/active-taxpayer-list-income-tax/51147/30859/71169`, opened in a new tab.
- **Rationale:** FBR's own page (Principle II), listing all three official checks: the online
  "ATL status check", SMS ("ATL (space) 13-digit CNIC" to 9966) and the downloadable list
  (checked 2026-11-04).
- **Alternatives:** the online check's own address (`e.fbr.gov.pk/esbn/Service.aspx?PID=…`: an
  opaque service id likely to change); checking ATL status from the app (needs the user's CNIC:
  Principle V).

## R13. Reading the profile and supported tax years

- **Decision:** `GET /api/profile` always returns `200` with
  `{"profile": null | {...}, "supported_tax_years": [...]}`. `SUPPORTED_TAX_YEARS = ("2025-26",)`
  in `backend/app/settings.py` is the one list (FR-017); feature 004 tests that every supported
  year has a rates module.
- **Rationale:** "no profile yet" is a normal state for the setup page, not an error, and the page
  needs the years either way.
- **Alternatives:** `404` when missing (the fetch helper would treat a normal state as an error);
  deriving years from 004's rates folder (004 is built after 002).

## R14. Enforcing the profile

- **Decision:** frontend `RequireProfile`, nested in `RequireAuth`, sends users without a profile
  to `/profile?next=<path>` (`/profile` itself is not wrapped). Backend: `get_profile(db, user)`
  returns the profile or `None`; `require_profile` returns it or answers `409`
  `{"detail": "Set up your profile first."}`.
- **Rationale:** FR-020 and FR-022: the UI guides, the backend enforces. `409` means "your account
  isn't in the state this needs", distinct from `401`.
- **Alternatives:** `403` (reads as a permissions problem); enforcing only in the UI (fails
  FR-022, SC-008).
