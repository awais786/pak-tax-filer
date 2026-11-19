---
description: "Tasks for feature 011: Admin Area"
---

# Tasks: Admin Area

**Input**: `specs/011-admin-area/` (plan.md, spec.md, research.md, data-model.md,
contracts/admin-pages.md, quickstart.md). Design: `docs/superpowers/specs/2026-11-17-admin-area-design.md`.

**Tests**: required (constitution Principle VI, `.claude/rules/testing-quality.md`): every
implementation task follows its test task, and the test is run and seen to fail for the right
reason first. Backend tests run in Docker: `docker compose exec -T backend pytest …`.

**Organization**: by user story (US1 see, US2 act, US3 telemetry), after shared setup.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3 (spec.md)

---

## Phase 1: Setup

- [X] T001 Add `starlette-admin>=1.0.3,<2` to `backend/pyproject.toml` with `uv add` (updates `backend/uv.lock`), rebuild the backend image (`docker compose build backend`, from PowerShell) and check `docker compose exec backend python -c "import starlette_admin"`; record the reason in the commit (research R1)
- [X] T002 Test first in `backend/tests/test_settings.py`: `ADMIN_SECRET_KEY` read into `admin_secret_key` (None when unset, absent from `repr`); `TELEMETRY_STORE` read into `telemetry_store` as `on`/`off` (default `on`, anything else refused like `OTEL_EXPORTER`); `backend/tests/conftest.py` sets `TELEMETRY_STORE=off` with `setdefault`, as it does for `OTEL_EXPORTER`
- [X] T003 Implement both settings in `backend/app/settings.py` (`admin_secret_key: str | None = field(default=None, repr=False)`, `telemetry_store: bool`) and the conftest default; CI's env in `.github/workflows/ci.yml` gets `TELEMETRY_STORE: off` beside `OTEL_EXPORTER: none`

---

## Phase 2: Foundational (blocks every story)

- [X] T004 Test first in `backend/tests/admin/test_models.py` (new package `backend/tests/admin/__init__.py` if the suite needs it): a new `User` has `is_admin` False and `disabled_at` None; an `AdminAuditEntry` and a `TelemetrySpan` round-trip; then let the contract check fail on the new `data-model.md` tables (`uv run --project backend python scripts/validate_contracts.py --feature 011` after ticking T001)
- [X] T005 Models and migration per `data-model.md`: `users.is_admin` "boolean, not null, default false" and `users.disabled_at` "timestamptz, null = active" in `backend/app/auth/models.py`; `AdminAuditEntry` (`admin_audit_log`: id uuid pk; admin_id uuid not null, **no foreign key**; action varchar not null, one of `view_account`, `disable`, `enable`, `delete_account`, `sign_out_everywhere`, `reset_reading_limit`; target_user_id uuid not null, **no foreign key**; at timestamptz not null default now(); index on `at`) in `backend/app/admin/audit.py`; `TelemetrySpan` (`telemetry_spans`, all columns as data-model.md; index on `started_at`) in `backend/app/telemetry/store.py`; make Alembic see the new models (`backend/alembic/env.py` imports as the others do); migration `backend/alembic/versions/0009_admin_area.py` (`--rev-id 0009`, autogenerate, reviewed by hand, server default false for existing users)
- [X] T006 [P] Test first in `backend/tests/auth/test_staff_only.py`: `POST /api/auth/login` with an admin account → 401 "Invalid email or password." and no cookie; with a disabled account → the same; `current_user` with a session belonging to an admin or a disabled account → 401 "Not logged in."; `tokens.service.owner_of` returns None for an admin's or a disabled account's token; `sessions.create_session(db, user, lifetime=timedelta(hours=8))` sets `expires_at` 8 hours ahead (default stays 7 days)
- [X] T007 Implement: `lifetime` parameter in `backend/app/auth/sessions.py`; the refusal in `backend/app/auth/router.py` (login, same message and throttle failure as a wrong password), `backend/app/auth/dependencies.py` (`current_user`), `backend/app/tokens/service.py` (`owner_of`)
- [X] T008 [P] Test first in `backend/tests/test_cli.py` (or the existing CLI test file): `create-admin --email` with the password typed twice creates an account with `is_admin` True; an existing email (any case) is refused with "A user with that email already exists." and exit 1; mismatched passwords refused as for `create-user`; nothing ever sets `is_admin` on an existing account
- [X] T009 Implement `create-admin` in `backend/app/cli.py`, reusing `create-user`'s prompting and `create_user`, then setting `is_admin`
- [X] T010 [P] Test first in `backend/tests/admin/test_audit.py`: `record(db, admin_id, action, target_id)` adds one entry with `at` set; an unknown action is refused; the module exposes no update or delete function; entries remain after the target and the admin accounts are deleted
- [X] T011 Implement `record()` in `backend/app/admin/audit.py`
- [X] T012 Test first in `backend/tests/admin/test_auth.py` (client over the app with the admin mounted): `/admin/` without a session redirects to `/admin/login`; an admin signs in and gets `admin_session` with `HttpOnly`, `SameSite=Strict`, `Path=/admin`, `Max-Age=28800` (and `Secure` when `COOKIE_SECURE` is true); taxpayer, wrong password, disabled, unknown email all show "Invalid email or password."; 10 failures for one email give "Too many attempts. Try again later." and are stored under `admin:`+email (the app's own login for that email still works); an app `session` cookie alone doesn't open `/admin`; an expired admin session doesn't; logout deletes the session row and clears the cookie
- [X] T013 Implement `AdminAuthProvider` in `backend/app/admin/auth.py` (research R2) and `build_admin(app)` in `backend/app/admin/__init__.py` (`Admin(session_provider=get_sessionmaker(), base_url="/admin", title="PakTaxFiler admin", auth_provider=..., secret_key=settings.admin_secret_key)`, one warning without the key when unset, `starlette_admin` logger set to WARNING per R13), called from `backend/app/main.py`; label the login field "Email" if the library allows (analyze U1)

**Checkpoint**: admins exist, sign in and out; taxpayer app refuses them.

---

## Phase 3: User Story 1 - See the app at a glance (P1) 🎯 MVP

**Goal**: dashboard, accounts with overview, documents, law library, audit log; read-only; account
views audited. **Independent test**: quickstart scenarios 1–4.

- [X] T014 [P] [US1] Test first in `backend/tests/admin/test_overview.py`: `dashboard_counts(db)` with synthetic data returns taxpayer accounts (admins excluded), profiles, documents per status (uploaded/confirmed/failed), guided runs per step, extraction attempts in the last 24 h (with the 10 and 100 limits), Ask questions in the last 24 h (with 200) and the busiest user's last hour (with 30); `account_overview(db, user)` returns profile (tax year, ATL), documents with status, the Tax result equal to what `GET /api/tax/{year}` returns for that user (figures or blocked reason, summary included), and the stored guided-run step; for a run whose inputs changed since it ran, `account_overview` leaves the `workflow_runs` row unchanged (step, fingerprint, `updated_at`)
- [X] T015 [US1] Implement `dashboard_counts` and `account_overview` in `backend/app/admin/overview.py` (Tax result via `app.tax.service.tax_inputs` + `app.tax.engine.calculate` + `app.tax.router.tax_out`; run read straight from `WorkflowRun`, never `workflow.service.get_run`)
- [X] T016 [P] [US1] Test first in `backend/tests/admin/test_pages.py` (signed-in admin): dashboard shows the counts; accounts list shows email, created, admin, disabled and searches by email; the account page shows the overview; opening it writes exactly one `view_account` entry for that admin and account, and list pages write none; documents list shows type, status, tax year, uploaded, owner email, with no detail page and no file link; law library lists each corpus document with its passage count; audit log lists entries newest first, with emails for existing accounts and ids for deleted ones; for every view, the create page, edit page, delete, export and import are refused or absent
- [X] T017 [P] [US1] Test first in `backend/tests/guardrails/test_admin_no_secrets.py`: with known synthetic password hashes, session tokens and access tokens in the database, fetch every admin page (dashboard, each list and detail, telemetry, audit log) and assert none of the hashes or token values appears
- [X] T018 [US1] Implement in `backend/app/admin/views.py`: `AccountView` (fields: email, created_at, is_admin, disabled_at; search on email; detail template `backend/app/admin/templates/account_detail.html` extending the library's detail with the overview panel; record lookup writes `view_account` when `request.state.action == RequestAction.DETAIL`), `DocumentView`, `CorpusDocumentView` (with passage counts), `AuditLogView`, dashboard as the index `CustomView` with `StatWidget`s; every view's `can_create/can_edit/can_delete/can_export/can_import` False, explicit `fields`; register them in `build_admin`
- [X] T019 [P] [US1] Test first in `deploy/tests/test_caddyfile.py`: `deploy/Caddyfile` sends `/admin` and `/admin/*` to `backend:8000` before the static handler and keeps the four security headers; `frontend/vite.config.ts` proxies `/admin` to `http://backend:8000`
- [X] T020 [US1] Implement the routing in `deploy/Caddyfile` and `frontend/vite.config.ts` (research R11)
- [X] T021 [US1] Research R12: if the installed `base.html` lets a local template drop the `rsms.me` font import cleanly, add the override under `backend/app/admin/templates/` with a test in `backend/tests/admin/test_pages.py` that no admin page references an outside host; otherwise record why in the PR

**Checkpoint**: US1 works on its own (quickstart 1–4).

---

## Phase 4: User Story 2 - Act on a taxpayer account (P2)

**Goal**: disable/re-enable, delete (files first), sign out everywhere, reset reading limit, each
audited, never on admins. **Independent test**: quickstart scenario 5.

- [X] T022 [P] [US2] Test first in `backend/tests/admin/test_actions.py`: `disable_account` sets `disabled_at`, deletes sessions and access tokens, and the user is then refused at login, by `current_user` and by `owner_of`; `enable_account` clears it (tokens stay gone); `delete_account` removes each document's stored file (local storage in tests) and then the user and everything that cascades; with storage raising `StorageUnavailable` on the second file it raises a clear error and no row is deleted, and a retry succeeds; deleting an already-deleted account reports it and writes no entry; `sign_out_everywhere` deletes sessions and keeps tokens; `reset_reading_limit` deletes the user's extraction attempts from the last 24 hours so `use_extraction` succeeds again; each function refuses an admin target; each completed action writes exactly one audit entry with the right action
- [X] T023 [US2] Implement the five functions in `backend/app/admin/actions.py` (research R7; files first through `app.documents.storage`; one transaction per action including its audit entry)
- [X] T024 [P] [US2] Test first in `backend/tests/admin/test_row_actions.py` (signed-in admin, CSRF token taken from the page): each row action on a taxpayer calls its function and shows the library's success message; Disable is offered only for active accounts and Re-enable only for disabled ones; no action is offered for an admin account (list and detail); a delete during a storage outage shows "Storage can't be reached; nothing was deleted. Try again later."; a form post without the CSRF token is refused
- [X] T025 [US2] Implement the row actions with the confirmations from `contracts/admin-pages.md` in `backend/app/admin/views.py` (`row_action`, `is_row_action_allowed_for_obj`)

**Checkpoint**: US2 works on its own (quickstart 5).

---

## Phase 5: User Story 3 - See how the app is performing (P3)

**Goal**: telemetry saved without content for 30 days and shown. **Independent test**: quickstart 6.

- [X] T026 [P] [US3] Test first in `backend/tests/telemetry/test_store.py`: the exporter, added through `add_exporter`, queues request spans and AI-call spans and drops database spans; a queued row holds only `data-model.md`'s columns filled from `ALLOWED` attributes (a span given an extra attribute keeps none of it); the queue is bounded at 10,000 and drops the oldest; `write_batch(db)` inserts the queued rows and creates no spans of its own (the engine listener skips while instrumentation is suppressed); a failing insert is logged without content and doesn't raise; `delete_old(db, now)` removes rows older than 30 days and keeps the rest; with `TELEMETRY_STORE=off` nothing is queued; a request succeeds while the writer fails
- [X] T027 [US3] Implement `backend/app/telemetry/store.py` (exporter, queue, `write_batch`, `delete_old`, the writer loop: every 5 s, clean-up hourly), the suppression check in `backend/app/telemetry/setup.py`'s engine listener, and a lifespan in `backend/app/main.py` that starts and stops the writer when `telemetry_store` is on
- [X] T028 [P] [US3] Test first in `backend/tests/admin/test_telemetry_page.py`: with known rows over several days, `telemetry_summary(db, now)` returns requests per day, the 5xx share, the slowest routes with median and 95th-percentile time, AI calls per feature by outcome, AI call duration, tokens per day, all for the last 30 days only; the telemetry page shows them
- [X] T029 [US3] Implement `telemetry_summary` in `backend/app/telemetry/store.py` and the `/admin/telemetry` `CustomView` (stat, chart and table widgets) in `backend/app/admin/views.py`

**Checkpoint**: all three stories work (quickstart 1–6).

---

## Phase 6: Polish & Cross-Cutting

- [X] T030 [P] Guardrail test first in `backend/tests/guardrails/test_admin_no_ai.py`: with the extractor, answerer and embedder faked to fail on any call, every admin page and all four actions work; then add the `app.admin` direct-import ban (`google`, `app.documents.extraction`, `app.rag.answer`, `app.rag.embed`, `app.rag.service`; `allow_indirect_imports = True`) to `.importlinter` and update `backend/tests/guardrails/README.md`
- [X] T031 [P] E2E test `e2e/tests/admin.spec.ts`: create an admin in the e2e stack (`docker compose -p pak-e2e … exec -T backend python -m app.cli create-admin`, password piped twice, from the test's setup or `e2e/README.md`'s steps), sign in at `/admin`, find a taxpayer created through the API, disable it, and check that taxpayer's app login is refused; e2e README updated
- [X] T032 [P] Docs: admin section in `backend/CLAUDE.md` (layout, staff-only rule, audit, telemetry store, no AI); README (admin area under the MVP scope, how to create the first admin); `docs/deployment.md` (set `ADMIN_SECRET_KEY` in the VM's `.env`, create the first admin with `docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin`); `docs/api-conventions.md` gets one line that `/admin` pages are outside the JSON API
- [X] T033 Final checks: backend `docker compose exec -T backend pytest` (full), `uv run ruff format --check .`, `uv run pylint --recursive=y app alembic evals tests`, `uv run mypy app alembic evals tests`, `uv run lint-imports`, contract check `--all`; frontend tests, `tsc -b`, lint; e2e suite on the `pak-e2e` stack; restart the dev frontend if needed, then smoke-test `http://localhost:5173/admin` (sign in as a throwaway synthetic admin, open every page, delete the throwaway accounts after)
- [X] T034 Reviews: `backend-reviewer` agent on the backend diff; `/speckit-converge` and `/speckit-analyze` before the PR; fix Medium and above
- [X] T035 (manual) Saifullah signs off the two rewritten 004 worked examples (`backend/tests/tax/worked_examples.yaml`, `bank-profit-outside-the-*`) before any push
- [X] T037 (manual) Open a `[011]` GitHub issue linking spec.md and tasks.md (constitution: Traceability), like #47 for 010; ask Saifullah before posting it
- [X] T036 (manual) One PR from `011-admin-area` (contains the 004 fix): "Needs your input" for the lead: starlette-admin instead of fastapi-admin, constitution 1.4.0, building before his spec/plan review, the 004 s.8(1)(a) change; ask Saifullah before pushing

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T013) → US1 (T014–T021) → US2 (T022–T025) → US3
  (T026–T029) → Polish (T030–T036).
- US2 needs US1's `AccountView` (its row actions live there); US3 is independent of US1/US2 except
  for `build_admin` (T013).
- Inside each pair, the test task comes first and must fail before its implementation.

## Parallel Opportunities

- T006, T008, T010 (different files) after T005.
- In US1: T014, T016, T017, T019 tests together; T020 alongside T015/T018.
- In US2: T022 and T024 tests together.
- In US3: T026 and T028 tests together.
- In Polish: T030, T031, T032.

## Implementation Strategy

MVP = Setup + Foundational + US1 (admins sign in and see everything, audited, read-only). Then US2
(actions), then US3 (telemetry). One commit per task, as in earlier features; everything ships in
one PR with the 004 fix.
