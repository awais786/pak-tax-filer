---

description: "Task list for feature 002: Authentication Foundation and Taxpayer Profile"
---

# Tasks: Authentication Foundation and Taxpayer Profile

**Input**: Design documents from `/specs/002-auth-foundation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
feature 001 implemented.

**Tests**: included and written first (constitution, Principle VI). Security behaviour
(generic errors, throttling, logout, expiry) is only trusted once a test proves it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1 to US5)

---

## Phase 1: Setup

- [X] T001 Add `pwdlib[argon2]` to `backend/pyproject.toml` with `uv add` and update `backend/uv.lock`
- [X] T002 [P] Add `react-router` to `frontend/package.json` with `npm install`
- [X] T003 [P] Add a proxy in `frontend/vite.config.ts` sending `/api` to `http://backend:8000`
- [X] T004 [P] Create `backend/app/settings.py`: reads `DATABASE_URL` and `COOKIE_SECURE` from the environment, with `COOKIE_SECURE` defaulting to `true` (safe by default); set `COOKIE_SECURE=false` only in the `backend` service of `docker-compose.yml` for local development

---

## Phase 2: Foundational

**Purpose**: database access, tables and test fixtures every story uses.

- [X] T005 Create `backend/app/db.py`: async SQLAlchemy engine from `settings.DATABASE_URL`, a declarative `Base`, and a `get_db` dependency yielding an `AsyncSession`
- [X] T006 Create `backend/app/auth/models.py` with `User`, `Session` and `LoginFailure` exactly as in [data-model.md](data-model.md): `users.email` "stored trimmed and lower-cased; unique"; `sessions.token_hash` "SHA-256 of the cookie token; unique"; `sessions.user_id` "deleted with the user"; `login_failures` indexed on `(email, attempted_at)`
- [X] T007 Create `backend/alembic/versions/0002_auth_tables.py` creating the three tables and indexes (revises `0001_enable_vector`); point `backend/alembic/env.py` at `Base.metadata`
- [X] T008 Create `backend/tests/conftest.py`: creates database `pak_tax_filer_test` if missing, runs `alembic upgrade head` on it once per test run, wraps each test in a rolled-back transaction, and provides an HTTPX `AsyncClient` with `get_db` overridden to that transaction
- [X] T009 [P] Write `backend/tests/auth/test_passwords.py`, then create `backend/app/auth/passwords.py` with `hash_password` and `verify_password` (pwdlib Argon2) plus `DUMMY_HASH` for unknown-email checks (research R5); tests assert the hash never equals or contains the password

**Checkpoint**: `alembic upgrade head` creates the tables; `pytest` passes.

---

## Phase 3: User Story 1 - Log in and log out (Priority: P1) 🎯 MVP

**Goal**: demo users can be created, log in and log out; guessing is throttled.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T010 [P] [US1] Write `backend/tests/auth/test_cli.py`: `create-user` creates a user with a lower-cased, trimmed email; refuses a duplicate in another letter case (exit 1, nothing created); refuses passwords under 8 characters or mismatched confirmation, per [contracts/cli-and-ui.md](contracts/cli-and-ui.md)
- [X] T011 [P] [US1] Write `backend/tests/auth/test_login_logout.py`, per [contracts/auth-api.md](contracts/auth-api.md): correct login (any email case) → `200`, `session` cookie with `HttpOnly` and `SameSite=Lax`, a `sessions` row whose `token_hash` is not the cookie value; wrong password and unknown email → identical `401` body; non-JSON request → refused; logout → `204`, cookie cleared, session row deleted, old cookie now gets `401` from `/api/auth/me`; two logins give two independent sessions
- [X] T012 [P] [US1] Write `backend/tests/auth/test_throttle.py`: 10 failures for an email → 11th attempt `429` even with the correct password, with the same message for unknown and known emails; failures older than 15 minutes don't count; a throttled attempt records no session

### Implementation for User Story 1

- [X] T013 [US1] Create `backend/app/auth/sessions.py`: `create_session(user)` returns a `secrets.token_urlsafe(32)` token and stores its SHA-256 hash with `expires_at` = now + 7 days; `get_user_for_token(token)` returns the user or `None` (deleting the row if expired); `delete_session(token)`
- [X] T014 [US1] Create `backend/app/auth/throttle.py`: `is_throttled(email)` (10+ failures in the last 15 minutes) and `record_failure(email)`
- [X] T015 [US1] Create `backend/app/auth/router.py` with `POST /api/auth/login` and `POST /api/auth/logout` per [contracts/auth-api.md](contracts/auth-api.md): normalize the email; check throttle first; verify against `DUMMY_HASH` when the email is unknown; record failures; set the cookie from research R2 with `Secure` from `settings.COOKIE_SECURE`; require `Content-Type: application/json`; include the router in `backend/app/main.py`; T011 and T012 pass
- [X] T016 [US1] Create `backend/app/cli.py` (`python -m app.cli create-user --email`, `argparse` + `getpass`, hidden password prompted twice); T010 passes
- [X] T017 [US1] Check that no password or session token is logged: add a test in `backend/tests/auth/test_login_logout.py` capturing log output during login and failed login and asserting neither value appears
- [X] T018 [US1] Run [quickstart.md](quickstart.md) section 1 and confirm each expected result

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - Protected APIs (Priority: P2)

**Goal**: one reusable protection that every later feature's endpoints use.

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [X] T019 [P] [US2] Write `backend/tests/auth/test_protected.py`: `GET /api/auth/me` with no cookie, an unknown token, a logged-out token, and a token whose `expires_at` is in the past → `401` `{"detail": "Not logged in."}`; with a valid token → `200` with only `{"email": ...}`

### Implementation for User Story 2

- [X] T020 [US2] Create `backend/app/auth/dependencies.py` with `current_user`: reads the `session` cookie, calls `get_user_for_token`, raises `401` "Not logged in." otherwise
- [X] T021 [US2] Add `GET /api/auth/me` to `backend/app/auth/router.py` using `current_user`, returning only the email; T019 passes
- [X] T022 [US2] Run [quickstart.md](quickstart.md) section 2

**Checkpoint**: User Story 2 works on its own.

---

## Phase 5: User Story 3 - Frontend integration (Priority: P3)

**Goal**: login page, protected pages, logout button, redirect when the session ends.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [X] T023 [P] [US3] Write `frontend/src/pages/LoginPage.test.tsx` (with `fetch` mocked): the demo-data notice and the "no password reset yet" note render; a successful login navigates to `next` or `/`; a `401` shows the server's message; a `429` shows "Too many attempts. Try again later."; opening `/login` while logged in goes to `/`
- [X] T024 [P] [US3] Write `frontend/src/pages/HomePage.test.tsx`: logged out → redirected to `/login?next=/`; logged in → shows "Logged in as <email>" and a logout button; logout → on `/login`; an API `401` → on `/login` with "Your session has ended, please log in again."

### Implementation for User Story 3

- [X] T025 [US3] Create `frontend/src/api/client.ts`: a `fetch` helper sending JSON with credentials, returning parsed JSON, and redirecting to `/login` with the session-ended message on `401` (except for the login request itself)
- [X] T026 [US3] Create `frontend/src/auth/AuthContext.tsx` (loads the user from `GET /api/auth/me`, exposes `user`, `login`, `logout`) and `frontend/src/auth/RequireAuth.tsx` (redirects to `/login?next=<path>`)
- [X] T027 [P] [US3] Create `frontend/src/pages/LoginPage.tsx` per [contracts/cli-and-ui.md](contracts/cli-and-ui.md), including the demo notice and redirect-if-logged-in; T023 passes
- [X] T028 [P] [US3] Create `frontend/src/components/LogoutButton.tsx` and `frontend/src/pages/HomePage.tsx` ("Logged in as <email>")
- [X] T029 [US3] Set up routes in `frontend/src/App.tsx` with React Router: `/login` and `/` wrapped in `RequireAuth`, inside `AuthContext`; replace 001's placeholder page; update `frontend/src/App.test.tsx` to match; T024 passes
- [X] T030 [US3] Run [quickstart.md](quickstart.md) section 3 in the browser

**Checkpoint**: all three stories work.

---

## Phase 6: User Story 4 - Set up the taxpayer profile on first login (Priority: P4)

**Goal**: a user without a profile is sent to the setup step, saves it, and reaches the app; the
backend enforces it (FR-016 to FR-020, FR-022, FR-023).

**Independent Test**: [quickstart.md](quickstart.md) section 4, steps 1–3 and 5.

### Tests for User Story 4 (write first, confirm they fail)

- [X] T034 [P] [US4] Write `backend/tests/profile/test_profile_service.py`: first save creates, second save replaces, two saves leave exactly one row, a `tax_year` outside `SUPPORTED_TAX_YEARS` raises
- [X] T035 [P] [US4] Write `backend/tests/profile/test_profile_api.py` per [contracts/auth-api.md](contracts/auth-api.md) (profile section): unauthenticated `GET`/`PUT` → `401`; `GET` with no profile → `200` `{"profile": null, "supported_tax_years": ["2025-26"]}`; valid `PUT` → `200`, then `GET` returns it; `tax_year` `2024-25` → `422` "Tax year 2024-25 is not supported."; missing or non-boolean `on_atl` → `422`; unknown field `cnic` → `422`; one user's `PUT` never changes another user's profile
- [X] T036 [P] [US4] Write `backend/tests/profile/test_require_profile.py`: a test-only endpoint using `require_profile` returns `409` `{"detail": "Set up your profile first."}` without a profile and receives the profile once saved
- [X] T037 [P] [US4] Write `frontend/src/pages/ProfilePage.test.tsx` (with `fetch` mocked) per [contracts/cli-and-ui.md](contracts/cli-and-ui.md): tax-year select lists only `supported_tax_years`; ATL has nothing selected and saving without it shows "Tell us whether you are on the ATL."; the FBR link has the research R12 URL and opens in a new tab; the residency notice and logout button are shown; a successful save navigates to `next` or `/`; a user without a profile opening `/` is redirected to `/profile?next=/`

### Implementation for User Story 4

- [X] T038 [US4] Add `SUPPORTED_TAX_YEARS` (tuple, default `("2025-26",)`) to `backend/app/settings.py`; create `backend/app/profile/models.py` with `TaxpayerProfile` exactly as in [data-model.md](data-model.md): `user_id` "references users.id, deleted with the user; unique"; `tax_year` "one of SUPPORTED_TAX_YEARS"; `on_atl` "required; no unknown value"; `updated_at` "set on every save"; no other columns; create it in a new migration `backend/alembic/versions/0003_taxpayer_profiles.py` (amended 2026-11-05: 0002 has already been applied, and applied migrations are never edited)
- [X] T039 [US4] Create `backend/app/profile/service.py` with `get_profile(db, user)` and `save_profile(db, user, tax_year, on_atl)` (one `INSERT … ON CONFLICT (user_id) DO UPDATE` that also sets `updated_at`, research R11); T034 passes
- [X] T040 [US4] Create `backend/app/profile/dependencies.py` (`require_profile`, research R14) and `backend/app/profile/router.py` (`GET`/`PUT /api/profile`, request model forbids extra fields); include the router in `backend/app/main.py`; T035 and T036 pass
- [X] T041 [US4] Create `frontend/src/profile/ProfileContext.tsx` (loads `GET /api/profile` after login; exposes `profile`, `supportedTaxYears`, `save`), `frontend/src/profile/RequireProfile.tsx` and `frontend/src/pages/ProfilePage.tsx` (with `LogoutButton`); in `frontend/src/App.tsx` add `/profile` under `RequireAuth` only and wrap every other `RequireAuth` route in `RequireProfile`; update `frontend/src/App.test.tsx`; T037 passes
- [X] T042 [US4] Run [quickstart.md](quickstart.md) section 4, steps 1–3 and 5

**Checkpoint**: new users must set up a profile.

---

## Phase 7: User Story 5 - Change the taxpayer profile (Priority: P5)

**Goal**: the saved profile can be reopened and changed (FR-021).

**Independent Test**: [quickstart.md](quickstart.md) section 4, step 4.

- [X] T043 [P] [US5] Extend `frontend/src/pages/ProfilePage.test.tsx`: with a saved profile the form shows the saved answers; changing ATL and saving sends the new value and shows it on reopening
- [X] T044 [P] [US5] Extend `backend/tests/profile/test_profile_api.py`: replacing a profile changes `on_atl` and `updated_at` but not `created_at`, and leaves the user's other rows unchanged (SC-009)
- [X] T045 [US5] Pre-fill `frontend/src/pages/ProfilePage.tsx` from the saved profile and add a "Profile" link next to the logout button on `frontend/src/pages/HomePage.tsx`; T043 and T044 pass
- [X] T046 [US5] Run [quickstart.md](quickstart.md) section 4, step 4

**Checkpoint**: all five stories work.

---

## Phase 8: Polish

- [X] T031 [P] Add an "Authentication" section to `CLAUDE.md`: protect new endpoints with `current_user`; never log passwords or tokens; how to create a demo user; read the profile with `get_profile`, refuse with `require_profile`, never add identity fields to it
- [X] T032 [P] Add "Create a demo user" to the README's development setup section
- [X] T033 Run Ruff and Prettier checks, both test suites, and all of [quickstart.md](quickstart.md); record results in the PR description

---

## Dependencies & Execution Order

- **Setup (T001–T004)** → **Foundational (T005–T009)** → stories.
- **US1** needs Foundational. **US2** needs US1's `sessions.py` (T013). **US3** needs US1 and US2
  endpoints to exist (its tests mock them, so T023–T024 can be written earlier).
- Within each story: tests → implementation → quickstart check.
- `backend/app/auth/router.py` is edited by T015 then T021, in that order.
- **US4** needs US2 (`current_user`) and US3 (`RequireAuth`, `App.tsx`); T038 adds to the
  `0002_auth_tables` migration from T007. **US5** needs US4.
- `ProfilePage.tsx` is edited by T041 then T045; `test_profile_api.py` by T035 then T044;
  `App.tsx` by T029 then T041.

## Parallel Opportunities

- Setup: T002, T003, T004 together after T001.
- US1 tests T010, T011, T012 together; US3 tests T023, T024 alongside US1/US2 work.
- T027 and T028 together; T031 and T032 together.
- US4 tests T034–T037 together; US5 tests T043, T044 together.

## Implementation Strategy

1. **MVP = User Story 1**: log in and out from the API with demo users.
2. **Add US2**: the `current_user` protection that every later feature uses.
3. **Add US3**: the browser experience.
4. **Add US4 and US5**: the taxpayer profile, required before 003's uploads and 004's tax page.
5. **Polish**, then one implementation PR.

GitHub issues for these tasks are titled `[002] T0NN: <description>`.
