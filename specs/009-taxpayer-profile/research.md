# Research: Taxpayer Profile (009)

Each decision: what was chosen, why, and what else was considered.

## R1. Storage

- **Decision:** a separate `taxpayer_profiles` table, `user_id` unique and referencing `users`
  (deleted with the user).
- **Rationale:** chosen in the design (approach A): keeps 002's `users` table login-only; the
  unique key enforces one profile per user (FR-001) in the database, not only in code.
- **Alternatives:** columns on `users` (reopens 002); one row per user and tax year (builds for
  years the MVP doesn't have; A → C later is one migration).

## R2. Saving: one upsert endpoint

- **Decision:** `PUT /api/profile` creates or replaces the profile with a single
  `INSERT … ON CONFLICT (user_id) DO UPDATE`.
- **Rationale:** one call for setup and edit; the database settles two saves arriving together
  (last write wins, still one row), covering the spec's two-tab edge case without locking.
- **Alternatives:** separate `POST` (create) and `PATCH` (edit) (two code paths for two fields);
  read-then-write in code (races).

## R3. Reading: always 200

- **Decision:** `GET /api/profile` returns `200` with `{"profile": null | {...},
  "supported_tax_years": [...]}`.
- **Rationale:** "no profile yet" is a normal state for the setup page, not an error; the page
  needs the supported years either way, so one call gives it everything.
- **Alternatives:** `404` when missing (the frontend client would treat a normal state as an
  error); a separate endpoint for supported years (an extra call for one list).

## R4. FBR ATL check link

- **Decision:** link to FBR's "Check Active Taxpayer Status" page,
  `https://www.fbr.gov.pk/categ/active-taxpayer-list-income-tax/51147/30859/71169`, opened in a
  new tab.
- **Rationale:** FBR's own page (Principle II) listing all three official checks: the online
  "ATL status check", SMS ("ATL (space) 13-digit CNIC" to 9966) and the downloadable list.
  Checked 2026-11-04. It explains the checks in plain words, so the user picks one.
- **Alternatives:** the online check itself
  (`https://e.fbr.gov.pk/esbn/Service.aspx?PID=…`: an opaque service ID likely to change, and
  it asks for a CNIC the app must never handle); checking ATL status from the app (would need the
  user's CNIC: Principle V).

## R5. Supported tax years

- **Decision:** `SUPPORTED_TAX_YEARS = ("2025-26",)` in `backend/app/settings.py`; the profile's
  choice and validation use it. In the follow-up phase, 003's single `TAX_YEAR` setting is
  replaced by the profile's year, and a test asserts every supported year has a 004 rates module.
- **Rationale:** one list (FR-003); the test stops a year being offered without FBR rates.
- **Alternatives:** deriving the list from 004's rates folder (009's core is built on 002, before
  004 necessarily exists); hard-coding the year in the page.

## R6. Enforcing the profile

- **Decision:**
  - **Frontend:** `RequireProfile`, nested inside 002's `RequireAuth`, sends a user without a
    profile to `/profile?next=<path>`; `/profile` itself and logout are not wrapped.
  - **Backend:** `require_profile` dependency returns the profile or answers `409`
    `{"detail": "Set up your profile first."}` (used by 003 uploads); `get_profile` returns the
    profile or `None` for callers that degrade instead of refusing (004 and 006 return
    `needs_atl_answer`).
- **Rationale:** FR-006 and FR-009: the UI guides, the backend enforces. `409` means "your
  account isn't in the state this needs", which is distinct from 002's `401`.
- **Alternatives:** `403` (reads as a permissions problem); enforcing only in the UI (fails
  FR-009 and SC-002).
