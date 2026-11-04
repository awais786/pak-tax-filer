# 001 Repo Foundations: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 001 (README milestone 1) ·
**Governed by:** [Constitution v1.2.0](../../../.specify/memory/constitution.md)

## Intent

README milestone 1: "Docker Compose skeleton, `CLAUDE.md`, Claude Code hooks (guard the
tax-rates module, format-on-write) and permission settings." This gives every later feature a
running, empty app and a Claude Code setup that enforces the constitution from day one. No
product features are built here.

## Scope

1. **Docker Compose skeleton:** `db` (PostgreSQL + pgvector), `backend` (FastAPI),
   `frontend` (React + TypeScript). Matches the README's setup section: `docker compose up -d`
   starts all three; backend on `http://localhost:8000`, frontend on `http://localhost:5173`;
   tests via `docker compose exec backend pytest` and `docker compose exec frontend npm test`.
2. **`CLAUDE.md`:** a short guide for Claude Code: the constitution's key rules, the repo
   layout, and the commands to run, test and format.
3. **Hooks** (shared, in `.claude/settings.json`):
   - **Tax-rates guard:** any attempt by Claude to change the tax-rates module pauses and asks
     the person at the keyboard to approve, explaining that rates must come from FBR's
     gazetted documents (Principle II). It asks; it does not block.
   - **Format-on-write:** every file Claude writes is formatted automatically.
4. **Permission settings** (shared): what Claude may do without asking, must ask about, and
   must never do.
5. **README setup section** updated for FastAPI (replacing the Django `manage.py` step).

## Out of scope

Auth, database tables, any tax logic, any real data.

## Addendum (2026-11-03): lead's issues #4 and #5

Added to this feature as User Story 4: CI in GitHub Actions (moved here from feature 008),
backend and frontend `CLAUDE.md` files, `.claude/rules/` by topic (architecture, backend,
frontend, API, testing, security), reusable skills (FastAPI feature, React feature, code
review), backend and frontend review subagents, and a written API convention. The issues name
OpenSpec; the lead agreed we stay on Spec Kit.

## Addendum (2026-11-04): building on the lead's #10

The lead merged #10 (root `CLAUDE.md`; rules `security`, `python-django`, `git-workflow`,
`testing-quality`; `settings.json` hooks: a git-safety guard and pylint/frontend-lint after
edits), which covers part of issue #5. This feature now **builds on #10 and only fills the
gaps**: it extends his `CLAUDE.md`, `settings.json` and rules instead of creating them; reuses
his `security` and `testing-quality` rules (no separate `security`/`testing` files); adds
`architecture`, `frontend` and `api` rules; and keeps the tax-rates guard, format-on-write,
permissions, folder guides, skills, reviewers, CI and the API convention. Decided by
Saifullah:

| Clash | Chosen | Rejected |
|---|---|---|
| Linter | **pylint lints** (his hook, and CI); **Ruff only formats** | Ruff for both (rewrites his hook); both linting (competing rules) |
| Hook style | **bash + `jq`, like his**; `jq` becomes a prerequisite | Python via `uv` (two styles in one repo) |
| `python-django.md` | **renamed `python-backend.md`, minimally edited for FastAPI + Alembic**, flagged in PR #3 for the lead | leaving it and adding `backend.md` (contradictory instructions) |

## Addendum (2026-11-04): contract validation (lead's issue #16)

The lead asked (issue #16) for automated contract validation: machine-checkable contracts,
Claude Code hooks that check them during implementation and refuse "done" while mandatory checks
fail, reusable scripts with proper exit codes, Spec Kit integration without duplicating it, and
the same scripts in CI blocking merges; smallest practical solution, existing tools reused. It is
project setup, so it joins this feature as **User Story 5** (as issues #4 and #5 became User
Story 4). Decided by Saifullah:

| Decision | Chosen | Rejected |
|---|---|---|
| Where | **Feature 001, User Story 5** | a separate chore PR (outside the 8-feature structure) |
| How contracts become checkable | **A. a small `contracts/api.yaml` (OpenAPI paths subset) per feature with an API, plus one script comparing it with the app's generated OpenAPI schema; the same script checks the MCP tool list and database tables** | B. contract tests only (checks only what someone remembered); C. OpenAPI snapshot + drift check (catches changes, not whether the app matches the spec) |

- **What is checked (deterministic):**
  - API: every path, method, status code and required field in each `api.yaml` exists in the
    app's OpenAPI schema (generated in-process, no server); endpoints in the app missing from
    every `api.yaml` are reported too.
  - MCP: exactly the three tools named in 006's contract.
  - Database: each table and column in a feature's `data-model.md` exists in the app's
    SQLAlchemy metadata (read from the existing Markdown tables, no extra file).
  - Spec Kit: a feature can't be called complete while its `tasks.md` has unchecked tasks.
- **Semantic review stays separate:** `speckit-converge` (compares code with spec, plan, tasks)
  and `speckit-analyze` run before a feature's PR; they are not pass/fail scripts.
- **Hook:** a Claude Code `Stop` hook runs the script for the features whose files changed in
  the session and blocks stopping with the script's messages while it fails; nothing runs after
  every edit (issue #16: no expensive checks per edit).
- **CI:** a `contracts` job runs the same script for all features; failing blocks merge.
- **Contract files for 001–008** are written now from their existing Markdown contracts, which
  are not changed (001's covers `/health`). *(Builder's call: issue #16 point 1, "identify and
  make machine-verifiable".)*
- **Which features are checked:** a feature is checked once it has started (at least one task
  ticked in its `tasks.md`); features not started are skipped, so CI is green while 002–008 are
  still specs. For a started feature, its contract checks must pass and, once its last task is
  ticked, no non-manual task may be unchecked. Endpoints in the app missing from every
  `api.yaml` fail the run, except FastAPI's own `/openapi.json`, `/docs`, `/redoc`.
  *(Builder's call.)*
- **Manual tasks** (a human check, a second OS, a deliberately failing PR) are marked `(manual)`
  in `tasks.md` and never counted by the script. *(Builder's call.)*
- **Hook behaviour:** the `Stop` hook checks the current branch's feature (Spec Kit's `NNN-`
  branch convention). Mid-feature it shows contract failures in the session without
  blocking; once the feature's last non-manual task is ticked (a completion claim) it **blocks**
  stopping until every check passes. *(Builder's call: issue #16 point 2, "not complete while
  failing".)*
- **Strictness:** checked from the OpenAPI schema: path, method, success status, required
  request fields and response fields. This adds one convention to `api-conventions.md`: every
  route declares a `response_model`. Error statuses (401, 404, 409, 429) are already covered by
  each feature's API tests, which the hook and CI run. *(Builder's call: avoids requiring every
  error response to be declared in code.)*
- **Blocking merges:** the `contracts` job only blocks once it is a required status check on
  `main`; that repository setting is the lead's, so the PR asks him to enable it (as T043 asks
  about his hook). *(Builder's call.)*
- **Docs:** a section in `CLAUDE.md` and `docs/contracts.md` on defining a contract, running the
  check locally and reading failures.

## Decisions

- **Guard behaviour:** ask for approval, not block (decided by Saifullah).
- **Layout:** `backend/` and `frontend/` at the repo root with `docker-compose.yml`, as the
  README's setup implies.
- **Tax-rates module path:** `backend/app/tax/rates/`, fixed now so the guard protects it
  before feature 004 fills it. *(Builder's call.)*
- **Hooks are written in Python**, so they run the same on Windows, macOS and Linux.
  *(Builder's call.)*
- **Tooling:** `uv` for Python dependencies; Vite for the frontend (its default port is
  5173); Ruff (Python) and Prettier (TypeScript) as formatters; pytest and Vitest behind the
  README's test commands. *(Builder's call; standard choices.)*
- **Permissions:** allow tests, linters, formatters and read-only git commands; ask before
  `git push` and deletions; deny reading `.env` files (constitution, Secrets).
  *(Builder's call.)*

## Approaches

The tax-rates guard could be a **Claude Code hook** (a script that runs before each file
change) or a **permission "ask" rule** on the folder. The README names hooks, and a hook can
explain *why* it is asking, so the guard is a hook.

## Done when

- `docker compose up -d` on a fresh clone starts `db`, `backend` and `frontend`.
- `GET http://localhost:8000/health` returns OK; `http://localhost:5173` shows a placeholder
  page; the `vector` extension is enabled in the database.
- `pytest` and `npm test` each run at least one passing test inside their containers.
- Editing a file under `backend/app/tax/rates/` through Claude triggers an approval prompt
  with the FBR reason.
- A file Claude writes comes out formatted.
- Claude cannot read `.env`.
- The README setup section works as written for FastAPI.

## Left to the plan

Database layer and migrations (likely SQLAlchemy + Alembic), Python and Node versions within
the README's minimums (3.12+, 20+), Dockerfile details, and the exact hook scripts.
