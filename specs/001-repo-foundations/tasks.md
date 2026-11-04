---

description: "Task list for feature 001: Repo Foundations"
---

# Tasks: Repo Foundations

**Input**: Design documents from `/specs/001-repo-foundations/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: included. The spec requires passing backend and frontend tests (FR-006), and the
two hooks are tested before they are written (constitution, Principle VI).

**Organization**: grouped by user story so each can be built and checked on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: create the project skeletons.

- [ ] T001 Create the directory layout from plan.md: `backend/app/`, `backend/tests/`, `backend/alembic/versions/`, `frontend/src/`, `.claude/hooks/tests/`
- [ ] T002 Create `backend/pyproject.toml` with uv (Python 3.13): dependencies `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`; dev dependencies `pytest`, `httpx`, `ruff` (formatting only), `pylint`, `mypy`; Ruff format, pylint, mypy and pytest config in the same file; generate `backend/uv.lock`
- [ ] T003 [P] Create the React + TypeScript app in `frontend/` from the Vite template; keep the template's ESLint setup and its `lint` script (the lead's `check-frontend.sh` runs it); add dev dependencies `vitest`, `@testing-library/react`, `jsdom`, `prettier`; set `"test": "vitest run"` in `frontend/package.json`; configure Vitest (jsdom) in `frontend/vite.config.ts`
- [ ] T004 [P] Create `.env.example` at the repo root with placeholder values only (`DATABASE_URL`, `ANTHROPIC_API_KEY=` left empty) and a comment that real values go in an uncommitted `.env`
- [ ] T005 [P] Add `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` and `dist/` to `.gitignore`

---

## Phase 2: Foundational

**Purpose**: the containers every story runs in. No story work starts before this is done.

- [ ] T006 [P] Create `backend/Dockerfile`: `python:3.13-slim`, install uv, `uv sync` from `backend/uv.lock`, run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- [ ] T007 [P] Create `frontend/Dockerfile`: `node:24-alpine`, `npm ci`, run `npm run dev -- --host 0.0.0.0 --port 5173`
- [ ] T008 Create `docker-compose.yml` with services `db` (`pgvector/pgvector:pg17`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres` and `POSTGRES_DB=pak_tax_filer` as local-development-only values, healthcheck with `pg_isready`, named volume), `backend` (builds `backend/`, port `8000:8000`, `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/pak_tax_filer`, waits for `db` healthy, mounts `./backend`), `frontend` (builds `frontend/`, port `5173:5173`, mounts `./frontend` with `node_modules` kept in the container); no service requires a `.env` file
- [ ] T009 Create `backend/app/__init__.py`, `backend/app/tax/__init__.py` and `backend/app/tax/rates/__init__.py`, with a docstring in the last one stating that this module holds TY rates sourced only from FBR's gazetted documents and is guarded (constitution, Principle II)

**Checkpoint**: `docker compose up -d` builds and starts all three containers.

---

## Phase 3: User Story 1 - Start the whole app with one command (Priority: P1) 🎯 MVP

**Goal**: one command starts db, backend and frontend; each shows it is alive.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T010 [P] [US1] Write `backend/tests/test_health.py`: `GET /health` returns `200` and exactly `{"status": "ok"}`, per [contracts/health.md](contracts/health.md)
- [ ] T011 [P] [US1] Write `frontend/src/App.test.tsx`: the placeholder page renders a heading containing "pak-tax-filer"

### Implementation for User Story 1

- [ ] T012 [US1] Create `backend/app/main.py`: FastAPI app with `GET /health` returning `{"status": "ok"}`; T010 passes
- [ ] T013 [US1] Replace the Vite starter in `frontend/src/App.tsx` with a placeholder page (heading "pak-tax-filer", one line saying the app is under construction); remove unused starter assets; T011 passes
- [ ] T014 [US1] Set up Alembic: `backend/alembic.ini` and an async `backend/alembic/env.py` that reads `DATABASE_URL` from the environment
- [ ] T015 [US1] Create `backend/alembic/versions/0001_enable_vector.py`: upgrade runs `CREATE EXTENSION IF NOT EXISTS vector`, downgrade runs `DROP EXTENSION IF EXISTS vector`
- [ ] T016 [US1] Run [quickstart.md](quickstart.md) section 1 and confirm every expected result

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - AI changes to tax rates need human approval (Priority: P2)

**Goal**: any Claude change to `backend/app/tax/rates/` pauses for approval with the FBR reason.

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T017 [P] [US2] Write `.claude/hooks/tests/test_tax_rates_guard.py`, feeding JSON events to `bash .claude/hooks/tax-rates-guard.sh` on standard input: `Edit`, `Write` and `MultiEdit` on a file inside the folder → `permissionDecision: "ask"` with the FBR reason from [contracts/claude-hooks.md](contracts/claude-hooks.md); `Bash` commands containing `backend/app/tax/rates` with `/` or `\` → `ask`; a file or command outside the folder → exit 0, no output; the hook never outputs `deny`

### Implementation for User Story 2

- [ ] T018 [US2] Create `.claude/hooks/tax-rates-guard.sh` (bash + `jq`, in the same style as the lead's `git-safety.sh`) implementing the `PreToolUse` contract in [contracts/claude-hooks.md](contracts/claude-hooks.md); T017 passes
- [ ] T019 [US2] In the lead's existing `.claude/settings.json` (#10), add a `hooks.PreToolUse` entry with matcher `Edit|Write|MultiEdit|Bash` and command `bash .claude/hooks/tax-rates-guard.sh`, keeping his `git-safety.sh` entry unchanged
- [ ] T020 [US2] Run [quickstart.md](quickstart.md) section 2 in Claude Code and confirm the prompt appears, reject leaves the file unchanged, and approve applies it

**Checkpoint**: User Story 2 works on its own.

---

## Phase 5: User Story 3 - The AI assistant follows the project's shared rules (Priority: P3)

**Goal**: shared guide, auto-formatting and permissions for every contributor.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T021 [P] [US3] Write `.claude/hooks/tests/test_format_on_write.py`, running `bash .claude/hooks/format-on-write.sh`: a badly formatted `.py` file is reformatted; a file with a syntax error is left unchanged and the failure is reported as `hookSpecificOutput.additionalContext`; a `.md` file is left alone

### Implementation for User Story 3

- [ ] T022 [US3] Create `.claude/hooks/format-on-write.sh` (bash + `jq`, like the lead's hooks) implementing the `PostToolUse` contract: `uvx ruff format` for `.py`; `npx --yes prettier --write` for `.ts`, `.tsx`, `.js`, `.jsx`, `.css`; formatting only (linting stays with the lead's hooks); T021 passes
- [ ] T023 [US3] In the lead's `.claude/settings.json`, add a `hooks.PostToolUse` entry with matcher `Edit|Write|MultiEdit` and command `bash .claude/hooks/format-on-write.sh`, keeping his `check-python.sh` and `check-frontend.sh` entries unchanged
- [ ] T024 [US3] Add a `permissions` section to the lead's `.claude/settings.json` exactly as in the table in [contracts/claude-hooks.md](contracts/claude-hooks.md): allow tests, linters, formatters, read-only git and `docker compose ps`/`logs`; ask for `git push`, `rm`, `git rm`; deny reading `.env` and `.env.*`
- [ ] T025 [P] [US3] Extend the lead's root `CLAUDE.md` (#10), keeping all of his content and `@` imports, with (about one page in total): the constitution's seven principles in one line each with a link to `.specify/memory/constitution.md`; the repo layout; commands to start the app, run migrations, run backend, frontend and hook tests (hook tests need bash and `jq`), lint and format; a note that `backend/app/tax/rates/` is guarded
- [ ] T026 [US3] Run [quickstart.md](quickstart.md) section 3 in Claude Code and confirm each expected result

**Checkpoint**: all three user stories work independently.

---

## Phase 6: User Story 4 - Shared engineering conventions and automated checks (Priority: P4)

**Goal**: the lead's issues #4 and #5: CI on every PR, folder guides, topic rules, skills,
review subagents and an API convention.

**Independent Test**: [quickstart.md](quickstart.md), section 5.

- [ ] T027 [US4] Create `.github/workflows/ci.yml` per research R8: on pull requests and pushes to `main`; job `backend` (uv, `ruff format --check`, `pylint app`, `mypy app`, `pytest` with a `pgvector/pgvector:pg17` service and `DATABASE_URL` set); job `frontend` (Node 24, `npm ci`, `prettier --check .`, `npm run lint`, `tsc --noEmit`, `npm test`); job `hooks` (`uv run --no-project --with pytest pytest .claude/hooks/tests`, with `jq` available; no lint or type checks for bash)
- [ ] T028 [US4] Push a branch with a deliberately failing backend test and one with a misformatted `.tsx` file; confirm each CI job fails and the PR shows it; delete both branches
- [ ] T029 [P] [US4] Write `docs/api-conventions.md` exactly as [contracts/api-conventions.md](contracts/api-conventions.md)
- [ ] T030 [P] [US4] Write `backend/CLAUDE.md` (layout of `backend/app/`, how to add an endpoint, migration commands, test database notes; no repetition of the root guide)
- [ ] T031 [P] [US4] Write `frontend/CLAUDE.md` (layout of `frontend/src/`, how to add a page, calling the API through one helper, test commands; no repetition of the root guide)
- [ ] T032 [P] [US4] Write `.claude/rules/architecture.md` (constitution Principles I and II in practice: no LLM maths, guarded rates); in the lead's existing `.claude/rules/security.md`, add only the points it lacks (e.g. never log secrets or passwords). No second security file
- [ ] T033 [US4] Rename the lead's `.claude/rules/python-django.md` to `.claude/rules/python-backend.md` with `git mv`; make minimal edits for FastAPI ("Alembic migrations" for "Django migrations", "routers/schemas" for "views/serializers") and add FastAPI points it lacks (`Decimal` for money, async SQLAlchemy); update its `@` import in the root `CLAUDE.md`; in the lead's `.claude/rules/testing-quality.md`, add only missing points (tests first, the test database). No `backend.md` or `testing.md`. List the rename and edits in the PR description for the lead
- [ ] T034 [P] [US4] Write `.claude/rules/frontend.md` (scoped to `frontend/**`) and `.claude/rules/api.md` (points to `docs/api-conventions.md`; contract updated in the same PR as the endpoint)
- [ ] T035 [P] [US4] Create skills `.claude/skills/fastapi-feature/SKILL.md` and `.claude/skills/react-feature/SKILL.md`: step-by-step for adding a feature slice (contract, then tests, then code, then run checks), following the rules above
- [ ] T036 [P] [US4] Create skill `.claude/skills/code-review/SKILL.md`: checklist covering architecture, security, business logic, test coverage and regressions (issue #4, rule 5); uses the reviewer subagents for backend and frontend parts
- [ ] T037 [P] [US4] Create subagents `.claude/agents/backend-reviewer.md` and `.claude/agents/frontend-reviewer.md`, read-only tools only, each reviewing against its rules, the API convention and the constitution
- [ ] T042 [P] [US4] Write `.claude/hooks/tests/test_lead_hooks.py` (per the 2026-11-04 clarification): the lead's `git-safety.sh` asks on a force-push and stays silent on `git status`; `check-python.sh` ignores non-`.py` files and finds pylint once the backend's host virtual environment exists (after T043); `check-frontend.sh` ignores files that aren't `.js`/`.jsx`/`.ts`/`.tsx`/`.vue`. Tests only; his scripts stay unchanged unless he accepts T043
- [ ] T043 [US4] The lead's lint hooks run on the host, but 001 installs dependencies inside the containers: in the PR #3 description, propose to the lead a small change to his `.claude/hooks/check-python.sh` so it also looks for pylint in `backend/.venv/bin` and `backend/.venv/Scripts` (Windows); apply it only if he agrees, otherwise document `uv tool install pylint` as the fallback in `backend/CLAUDE.md` (T030)
- [ ] T038 [US4] Add a "Conventions" section to the root `CLAUDE.md` (after the lead's content) linking the folder guides, rules, skills and subagents and saying when to use each; run [quickstart.md](quickstart.md) section 5

**Checkpoint**: all four user stories work.

---

## Phase 7: User Story 5 - Contracts are checked automatically (Priority: P5)

**Goal**: the lead's issue #16: machine-checkable contracts checked by one script, a completion
hook and CI (FR-021 to FR-027).

**Independent Test**: [quickstart.md](quickstart.md) section 6.

### Tests for User Story 5 (write first, confirm they fail)

- [ ] T044 [P] [US5] Write `scripts/tests/test_validate_contracts.py` (pytest, a small sample FastAPI app and sample `specs/` folders) per research R11: a missing path, method, success status, required request field or required response field → exit 1 with `[NNN] file: item: problem`; an app endpoint in no `api.yaml` → exit 1, but `/openapi.json`, `/docs`, `/redoc` are allowed; a feature with no ticked task is skipped; a started feature with an API but no `api.yaml` → exit 1; a table or column in `data-model.md` missing from the metadata → exit 1; an MCP tool list not equal to the `mcp-tools.md` headings → exit 1; all non-manual tasks ticked except one → exit 1; `(manual)` tasks ignored; invalid YAML or an app that can't be imported → exit 2; everything matching → exit 0
- [ ] T045 [P] [US5] Write `.claude/hooks/tests/test_contracts_gate.py` per [contracts/claude-hooks.md](contracts/claude-hooks.md) (contract gate) with a stubbed check: non-feature branch → no output; pass → no output; violations mid-feature → `systemMessage`, exit 0; violations with every non-manual task ticked → `decision: block` with the messages; check exit 2 → `systemMessage`, never block

### Implementation for User Story 5

- [ ] T046 [US5] Create `scripts/validate_contracts.py` per research R11 (`--feature NNN` / `--all`; exit codes 0/1/2; started-feature and `(manual)` rules); add `pyyaml` to `backend/pyproject.toml` dev dependencies; T044 passes
- [ ] T047 [US5] Create `.claude/hooks/contracts-gate.sh` per research R12 and register it under `Stop` in `.claude/settings.json` beside the lead's entries (his are not changed); T045 passes
- [ ] T048 [US5] Add job `contracts` to `.github/workflows/ci.yml` (every pull request and push to `main`): `uv run --project backend python scripts/validate_contracts.py --all`
- [ ] T049 [P] [US5] Add the "Machine-checkable contract" rule to `docs/api-conventions.md` per [contracts/api-conventions.md](contracts/api-conventions.md) (every route declares `response_model`; `api.yaml` changes with the Markdown contract); make `GET /health` in `backend/app/main.py` declare its `response_model`
- [ ] T050 [P] [US5] Write `docs/contracts.md` (defining a contract and `api.yaml`; running the check locally; reading `[NNN] file: item: problem` messages; the started-feature and `(manual)` rules; the completion hook) and add a "Contracts" section to the root `CLAUDE.md`: run the check before claiming a feature done, and run `/speckit-converge` and `/speckit-analyze` before a feature's pull request
- [ ] T051 [US5] Mark this feature's human-only tasks `(manual)` in this `tasks.md` (T020, T026, T028, T041, T043, T052, T053 and the quickstart runs), per research R13
- [ ] T052 [US5] (manual) In this feature's pull request description, ask the lead to make the `contracts` CI job a required status check on `main` (repository setting)
- [ ] T053 [US5] (manual) Run [quickstart.md](quickstart.md) section 6, including every planted violation

**Checkpoint**: all five user stories work.

---

## Phase 8: Polish

- [ ] T039 Update the "Development setup" section of `README.md`: prerequisites Docker + Docker Compose, `uv`, Node 24+, bash and `jq`; for contributors using Claude Code, the host steps `uv sync` in `backend/` and `npm ci` in `frontend/` so the lead's lint hooks can run pylint and `npm run lint` on the host; replace `python manage.py migrate` with `alembic upgrade head`; add the hook test command; leave the rest of the README unchanged
- [ ] T040 [P] Run `ruff format --check`, `pylint app` and `mypy app` in `backend/`; `prettier --check`, `npm run lint` and `tsc --noEmit` in `frontend/`; and the hook tests; fix anything reported
- [ ] T041 Run the whole of [quickstart.md](quickstart.md) from a fresh clone, plus two extra checks: start the app with port 8000 already in use and confirm the error names the port; and run section 4 on a second operating system if one is available. Record the results in the PR description, stating plainly which operating systems were not checked so the lead can verify them

---

## Dependencies & Execution Order

- **Setup (T001–T005)** → **Foundational (T006–T009)** → user stories.
- **US1** depends only on Foundational.
- **US2 and US3** need only T001 and T009 (the reserved folder), so they can run alongside US1.
- **`.claude/settings.json`** (the lead's file) is extended by T019, T023 and T024, so those run in that order; his entries are never removed.
- The root **`CLAUDE.md`** (the lead's file) is extended by T025, then T033 (import rename), then T038.
- **US4** needs US1 (something for CI to check) and T025 (root `CLAUDE.md`); T029 to T037 and T042 can be written in parallel, except T033, which edits the root `CLAUDE.md` after T025.
- **US5** needs US1 (an app to check), US3 (`.claude/settings.json` from T019/T023/T024) and US4 (the CI workflow and T038's `CLAUDE.md`); T044 and T045 can be written in parallel; T047 extends `settings.json` after T024, and T050 extends `CLAUDE.md` after T038.
- **Polish** comes after all stories.
- Within each story: tests → implementation → quickstart check.

## Parallel Opportunities

- Setup: T003, T004, T005 together after T001/T002.
- Foundational: T006 and T007 together.
- US1: T010 and T011 together.
- Across stories: T017 (US2) and T021, T025 (US3) can be written while US1 is in progress.

## Implementation Strategy

1. **MVP = User Story 1**: Setup → Foundational → US1, then stop and validate with quickstart
   section 1. The app runs.
2. **Add US2**: the tax-rates guard, before feature 004 ever adds rates.
3. **Add US3**: formatting, permissions and `CLAUDE.md`.
4. **Add US4**: CI and the shared conventions from the lead's issues #4 and #5.
5. **Add US5**: contract checks from the lead's issue #16.
6. **Polish**, then one PR for the implementation.

GitHub issues for these tasks are titled `[001] T0NN: <description>` so they can't clash with
other features' task numbers.
