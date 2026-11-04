# Tasks: Taxpayer Profile

**Input**: Design documents from `/specs/009-taxpayer-profile/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/profile-api.md,
quickstart.md

**Tests**: required (constitution Principle VI); each story's tests are written first and must
fail before its code.

**Organization**: by user story. Phases 1–5 need only 002. **Phase 6 is done after 003–006 are
built.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- **[Story]**: which user story (US1, US2, US3)

---

## Phase 1: Setup

- [ ] T001 Add `SUPPORTED_TAX_YEARS` to `backend/app/settings.py`, a tuple defaulting to `("2025-26",)` (research R5)

---

## Phase 2: Foundational

**Purpose**: the table and service every story uses.

- [ ] T002 Create `backend/app/profile/models.py` with `TaxpayerProfile` exactly as in [data-model.md](data-model.md): `id` "UUID, primary key"; `user_id` "UUID, not null, unique, references users.id on delete cascade"; `tax_year` "text, not null"; `on_atl` "boolean, not null"; `created_at` and `updated_at` "timestamp with time zone, not null, default now", `updated_at` "set on every save"; no other columns
- [ ] T003 Create `backend/alembic/versions/0009_taxpayer_profiles.py` creating the table and the unique key on `user_id` (revises the latest migration present; downgrade drops the table)
- [ ] T004 Write `backend/tests/profile/test_profile_service.py`, then create `backend/app/profile/service.py` with `get_profile(db, user)` (profile or `None`) and `save_profile(db, user, tax_year, on_atl)` using one `INSERT … ON CONFLICT (user_id) DO UPDATE` that also sets `updated_at` (research R2); tests: first save creates, second save replaces, two saves leave exactly one row, `tax_year` outside `SUPPORTED_TAX_YEARS` raises

**Checkpoint**: profiles can be stored and read in code.

---

## Phase 3: User Story 1 - Set up the profile on first login (Priority: P1) 🎯 MVP

**Goal**: a user without a profile is sent to the setup step, saves it, and reaches the app; the
backend enforces it.

**Independent Test**: [quickstart.md](quickstart.md) scenarios 1–3 and 5.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T005 [P] [US1] Write `backend/tests/profile/test_profile_api.py` per [contracts/profile-api.md](contracts/profile-api.md): unauthenticated `GET`/`PUT` → `401`; `GET` with no profile → `200` `{"profile": null, "supported_tax_years": ["2025-26"]}`; `PUT` valid → `200` with the profile, then `GET` returns it; `tax_year` `2024-25` → `422` "Tax year 2024-25 is not supported."; missing or non-boolean `on_atl` → `422`; an unknown field such as `cnic` → `422`; one user's `PUT` never changes another user's profile
- [ ] T006 [P] [US1] Write `backend/tests/profile/test_require_profile.py`: a test-only endpoint using `require_profile` returns `409` `{"detail": "Set up your profile first."}` without a profile and receives the profile once saved
- [ ] T007 [P] [US1] Write `frontend/src/pages/ProfilePage.test.tsx` (with `fetch` mocked): tax-year select lists only `supported_tax_years`; ATL yes/no has nothing selected and saving without it shows "Tell us whether you are on the ATL."; the FBR link has the research R4 URL and opens in a new tab; the residency notice "This app covers people who live in Pakistan and earn a salary." is shown; a successful save navigates to `next` or `/`; a user without a profile opening `/` is redirected to `/profile?next=/`; the logout button is shown on the setup step and logs out

### Implementation for User Story 1

- [ ] T008 [US1] Create `backend/app/profile/dependencies.py` with `require_profile` (uses `current_user` and `get_profile`; raises `409` "Set up your profile first.") per research R6; T006 passes
- [ ] T009 [US1] Create `backend/app/profile/router.py` with `GET /api/profile` and `PUT /api/profile` per [contracts/profile-api.md](contracts/profile-api.md) (request model forbids extra fields); include it in `backend/app/main.py`; T005 passes
- [ ] T010 [US1] Create `frontend/src/profile/ProfileContext.tsx` (loads `GET /api/profile` after login; exposes `profile`, `supportedTaxYears`, `save`) and `frontend/src/profile/RequireProfile.tsx` (redirects to `/profile?next=<path>` when `profile` is `null`)
- [ ] T011 [US1] Create `frontend/src/pages/ProfilePage.tsx` per [contracts/profile-api.md](contracts/profile-api.md), including 002's `LogoutButton`; in `frontend/src/App.tsx` add `/profile` under `RequireAuth` only and wrap every other `RequireAuth` route in `RequireProfile`, inside `ProfileContext`; update `frontend/src/App.test.tsx`; T007 passes
- [ ] T012 [US1] Run [quickstart.md](quickstart.md) scenarios 1–3 and 5

**Checkpoint**: new users must set up a profile; MVP of this feature.

---

## Phase 4: User Story 2 - Change the profile later (Priority: P2)

**Goal**: the saved profile can be reopened and changed.

**Independent Test**: [quickstart.md](quickstart.md) scenario 4.

- [ ] T013 [P] [US2] Extend `frontend/src/pages/ProfilePage.test.tsx`: with a saved profile, the form shows the saved answers; changing ATL and saving sends the new value and shows it on reopening
- [ ] T014 [P] [US2] Extend `backend/tests/profile/test_profile_api.py`: replacing a profile changes `on_atl` and `updated_at` but not `created_at`, and leaves other tables' rows for the user unchanged (FR-008, SC-004)
- [ ] T015 [US2] Pre-fill `frontend/src/pages/ProfilePage.tsx` from the saved profile and add a "Profile" link next to the logout button on `frontend/src/pages/HomePage.tsx`; T013 and T014 pass
- [ ] T016 [US2] Run [quickstart.md](quickstart.md) scenario 4

**Checkpoint**: setup and edit both work, on 002 alone.

---

## Phase 5: Polish (needs only 002)

- [ ] T017 [P] Add a "Taxpayer profile" section to `CLAUDE.md`: read the profile with `get_profile`; refuse with `require_profile`; never add identity fields to it
- [ ] T018 Run the lint, format and type checks (001's CI), both test suites, and quickstart scenarios 1–5; record results in the PR description

---

## Phase 6: User Story 3 - Earlier features use the profile (Priority: P3) — after 003–006 are built

**Goal**: 003–006 read tax year and ATL status from the profile (FR-010 to FR-013).

**Independent Test**: [quickstart.md](quickstart.md) scenario 6.

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T019 [P] [US3] Extend 003's `backend/tests/documents/` tests: upload without a profile → `409` "Set up your profile first."; the upload's `tax_year` equals the profile's; a certificate year differing from the profile's is flagged by the tax-year consistency rule
- [ ] T020 [P] [US3] Extend `backend/tests/tax/test_tax_api.py`: the `atl` query parameter is no longer accepted; the result uses the profile's `on_atl`; no profile → `blocked_reason` `needs_atl_answer` with message "Set your ATL status in your profile."; and `frontend/src/pages/TaxPage.test.tsx`: no ATL question; the blocked message links to `/profile`
- [ ] T021 [P] [US3] Extend `frontend/src/pages/WealthPage.test.tsx`: the page opens on the profile's tax year
- [ ] T022 [P] [US3] Extend `backend/tests/mcp/test_mcp_tools.py`: `calculate_income_tax` takes no `tax_year` or `atl` input and returns the same body as `GET /api/tax/{profile year}` for the token owner; a token owner without a profile gets the `needs_atl_answer` body; `validate_salary_information` flags a certificate year differing from the owner's profile
- [ ] T023 [P] [US3] Write `backend/tests/profile/test_supported_years.py`: every year in `SUPPORTED_TAX_YEARS` has a rates module in `backend/app/tax/rates/` (research R5)

### Implementation for User Story 3

- [ ] T024 [US3] In `backend/app/documents/router.py` and `service.py`, depend on `require_profile`, stamp uploads with the profile's `tax_year`, and compare 003's tax-year rule in `backend/app/documents/extraction/rules.py` with it; remove `TAX_YEAR` from `backend/app/settings.py`; T019 passes
- [ ] T025 [US3] In `backend/app/tax/service.py` and its router, drop the `atl` parameter and read `on_atl` via `get_profile`, returning `needs_atl_answer` with the new message when there is no profile; remove the ATL question from `frontend/src/pages/TaxPage.tsx` and link the blocked message to `/profile`; T020 passes
- [ ] T026 [US3] Make `frontend/src/pages/WealthPage.tsx` (and its route in `frontend/src/App.tsx`) use the profile's tax year from `ProfileContext`; T021 passes
- [ ] T027 [US3] In `backend/app/mcp_server/__main__.py`, remove `tax_year` and `atl` from `calculate_income_tax`'s input schema and read the token owner's profile; check `validate_salary_information`'s `tax_year` against it; T022 and T023 pass
- [ ] T028 [US3] Search the frontend and MCP tool descriptions for any remaining ATL or tax-year prompt outside `/profile` (SC-005); run [quickstart.md](quickstart.md) scenario 6 and both test suites; record results in that PR's description

**Checkpoint**: no screen or tool asks for ATL or tax year except the profile.

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T004)** → **US1** → **US2** → **Polish**: needs only
  002.
- **Phase 6 (US3)** needs 003, 004, 005 and 006 built, plus Phases 1–4; it is a separate,
  later implementation PR.
- `ProfilePage.tsx` is edited by T011 then T015; `test_profile_api.py` by T005 then T014;
  `App.tsx` by T011 then T026.

## Parallel Opportunities

- US1 tests T005, T006, T007 together; US2 tests T013, T014 together.
- US3 tests T019–T023 together; implementation T024–T027 touch different features and can run
  in parallel once their tests exist.

## Implementation Strategy

1. **MVP = US1**: the profile exists and is required.
2. **Add US2**: editing.
3. **Polish**, then the first implementation PR (after 002).
4. **US3** as its own PR once 003–006 are built.

GitHub issues for these tasks are titled `[009] T0NN: <description>`.
