# Research: Repo Foundations (001)

Each decision: what was chosen, why, and what else was considered.

## R1. Runtime versions

- **Decision:** Python 3.13, Node 26 (LTS), PostgreSQL 17 with pgvector. *(Amended
  2026-11-05: planned as Node 24, but Node 26 became the current LTS in October 2026; it is
  also what the host installs, so container and host match.)*
- **Rationale:** the README sets minimums (Python 3.12+, Node 20+). Node 20 reached end of
  life in April 2026, so the current LTS is used. Python 3.13 is current and widely supported
  by libraries. PostgreSQL 17 is current and has an official pgvector image.
- **Alternatives:** Python 3.12 (security fixes only now); Python 3.14 (newest, library
  support still catching up); Node 24 (previous LTS, supported until 2028; the original choice).

## R2. Backend tooling

- **Decision:** `uv` for dependencies and running; Uvicorn as the server; pytest + FastAPI's
  `TestClient` (on `httpx2`) for tests; Ruff for formatting; pylint for linting (amended
  2026-11-04: the lead's #10 hook lints with pylint, so Ruff no longer lints; amended
  2026-11-05: Starlette now deprecates `httpx` for the test client in favour of `httpx2`).
- **Rationale:** `uv` is fast, handles Python versions, and is already used on the dev machine.
  These are FastAPI's documented defaults. Ruff formats in one fast tool (replacing Black and
  isort); pylint is the repo's existing linter, so we don't add a competing one.
- **Alternatives:** pip + venv (slower, no lockfile by default); Poetry (heavier); Black +
  isort for formatting (two tools instead of one); Ruff for linting too (the original decision;
  competes with the lead's pylint hook).

## R3. Database layer (for features 002+)

- **Decision:** SQLAlchemy 2.0 (async, with `asyncpg`) and Alembic for migrations. 001 sets up
  Alembic with a single migration that enables the `vector` extension; no tables.
- **Rationale:** the standard FastAPI pairing; pgvector has first-class SQLAlchemy support;
  async fits FastAPI. Enabling the extension in a migration (rather than a Docker init script)
  means every database, not only a fresh Docker volume, gets it, and the README's
  `manage.py migrate` step maps directly to `alembic upgrade head`.
- **Alternatives:** SQLModel (thin layer over SQLAlchemy, fewer docs for advanced cases);
  Docker `initdb` script for the extension (only runs on an empty volume).

## R4. Frontend tooling

- **Decision:** Vite (React + TypeScript template), Vitest + React Testing Library, Prettier
  for formatting, and the template's own linter (`npm run lint`) for linting: **oxlint**
  (amended 2026-11-05: Vite's React + TypeScript template now ships oxlint instead of ESLint;
  the plan's intent was "keep the template's linter", and the lead's hook runs `npm run lint`
  whichever linter is behind it).
- **Rationale:** Vite's dev server defaults to port 5173, matching the README; Vitest shares
  Vite's config, so `npm test` needs no extra setup. The lead's `check-frontend.sh` hook runs
  the frontend's `lint` script, which the Vite template provides (amended 2026-11-04).
- **Alternatives:** Create React App (deprecated); Jest (separate config for TypeScript/ESM).

## R5. Claude Code hooks: mechanism and language (amended 2026-11-04)

- **Decision:** two hooks, written in **bash + `jq` like the lead's #10 hooks**, saved as
  `.claude/hooks/tax-rates-guard.sh` and `.claude/hooks/format-on-write.sh`, and registered in
  the lead's existing `.claude/settings.json` **alongside** his entries (his are not changed).
  - **Tax-rates guard:** a `PreToolUse` hook on `Edit`, `Write`, `MultiEdit` and `Bash`. If the
    target path (or, for `Bash`, the command text) refers to `backend/app/tax/rates/`, it
    returns `permissionDecision: "ask"` with the FBR reason. Otherwise it returns nothing and
    normal rules apply.
  - **Format-on-write:** a `PostToolUse` hook on `Edit`, `Write`, `MultiEdit`. Runs
    `uvx ruff format` for `.py` files and `npx prettier --write` for `.ts`, `.tsx`, `.js`,
    `.jsx`, `.css`. It formats only; linting stays with the lead's `check-python.sh` (pylint)
    and `check-frontend.sh` (the frontend's `lint` script). If the formatter fails, the file is
    left as written and the failure is reported back to Claude as `additionalContext`, the same
    way his hooks report.
- **Rationale:** one hook style in the repo (his rules: don't introduce a competing
  convention). His hooks already require bash and `jq`, and Claude Code on Windows runs hooks
  through Git Bash, so the cross-platform reason for Python no longer applies.
- **Alternatives:** Python via `uv` (the original 2026-11-03 decision: works everywhere, but
  would put two hook styles side by side); a permission `ask` rule on the folder (can't give
  the FBR reason or see shell commands); running formatters inside the containers (would
  require the stack to be running while editing).
- **Consequence:** `uv`, Node, bash and `jq` are host prerequisites for contributors using
  Claude Code; the README lists them. The lead's lint hooks also run on the host, so those
  contributors run `uv sync` in `backend/` and `npm ci` in `frontend/` once; his
  `check-python.sh` only looks for pylint in `<repo>/.venv`, `venv` or the PATH, so a small
  change to also check `backend/.venv` is proposed to him (tasks T043), not made by us.

## R6. Permissions

- **Decision:** shared `permissions` added to the lead's `.claude/settings.json` (amended
  2026-11-04: his file already exists and has no permissions section):
  - **allow:** pytest, Ruff, pylint, Vitest/`npm test`, `npm run lint`, Prettier, read-only git (`status`, `diff`,
    `log`, `show`, `branch`), `docker compose ps`/`logs`;
  - **ask:** `git push`, file deletion (`rm`, `git rm`);
  - **deny:** reading `.env` and `.env.*`.
  Personal overrides stay in the git-ignored `.claude/settings.local.json`.
- **Rationale:** matches the spec (FR-011) and the constitution's Secrets rule.
- **Alternatives:** allow everything (unsafe); per-developer settings only (not shared, so
  FR-012 fails).

## R7. Health check

- **Decision:** `GET /health` returns `200` with `{"status": "ok"}`.
- **Rationale:** the simplest common convention; enough for the spec (FR-003). Database
  connectivity checks come with the first feature that uses the database.

## R8. CI (added for issues #4/#5; amended 2026-11-04)

- **Decision:** one GitHub Actions workflow, `.github/workflows/ci.yml`, on every pull request
  and push to `main`, with three jobs: **backend** (uv; `ruff format --check`, `pylint app`,
  `mypy app`, `pytest` against a PostgreSQL + pgvector service container), **frontend**
  (`npm ci`, `prettier --check`, `npm run lint`, `tsc -b`, `npm test`) and **hooks**
  (`pytest .claude/hooks/tests`, which runs every hook, ours and the lead's, against sample JSON
  inputs; no lint or type checks for bash, per the 2026-11-04 clarification). The eval gate is
  added when the first eval exists (003, 006).
- **Rationale:** the constitution's merge gate needs lint, type checks and tests; CI uses the
  same tools as the hooks (pylint and oxlint lint; Ruff and Prettier format), so local and CI
  results agree (spec FR-015). Separate jobs run in parallel and show exactly which part
  failed. Running Postgres as a service container matches the real database.
- **Alternatives:** `ruff check` as the linter (the original decision; would compete with the
  lead's pylint hook); ShellCheck on the hooks (a tool neither setup uses); one combined job
  (slower, unclear failures); running CI through Docker Compose (slower startup, harder
  caching); Pyright instead of mypy (either works; mypy is the more common default with
  SQLAlchemy and Pydantic plugins).

## R9. Claude Code conventions layout (added for issues #4/#5; amended 2026-11-04)

- **Decision:**
  - **Root `CLAUDE.md`:** the lead's file from #10, **extended**, not replaced: his engineering
    rules stay; we add the constitution's principles (one line each, linked), the repo layout,
    the run/test/format commands, and a "Conventions" section linking the folder guides, rules,
    skills and reviewers.
  - `backend/CLAUDE.md` and `frontend/CLAUDE.md`: short folder guides, loaded when Claude works
    in that folder; they don't repeat the root `CLAUDE.md`.
  - `.claude/rules/`: the lead's `security.md`, `git-workflow.md` and `testing-quality.md`
    are kept (project points they miss are added to them, not to new files); his
    `python-django.md` is **renamed `python-backend.md`** with minimal edits for FastAPI
    ("Alembic migrations", "routers/schemas"), the `@` import in `CLAUDE.md` updated, and the
    change flagged in PR #3 for him. New files only for topics his don't cover:
    `architecture.md`, `frontend.md` (scoped to `frontend/**` with `paths` front matter),
    `api.md`. No `backend.md`, `testing.md` or second `security.md`.
  - `.claude/skills/`: `fastapi-feature`, `react-feature`, `code-review` (next to the existing
    `speckit-*` skills).
  - `.claude/agents/`: `backend-reviewer.md`, `frontend-reviewer.md`, each with read-only tools.
- **Rationale:** these are Claude Code's own locations for each kind of guidance, so they load
  automatically; one concern per file keeps each short and avoids duplication (issue #5);
  building on #10 avoids two files on the same topic.
- **Alternatives:** our own six rule files (the original decision; would duplicate his
  `security` and `testing-quality` and contradict his Django file); one long `CLAUDE.md` (hard
  to maintain, always fully loaded); reviewers with write access (a reviewer should report,
  not change code).

## R10. API convention (added for issue #4)

- **Decision:** `docs/api-conventions.md` is the written standard (see
  [contracts/api-conventions.md](contracts/api-conventions.md)); `.claude/rules/api.md` points to
  it. Each feature's API contract lives in its `specs/NNN-*/contracts/` and follows it. FastAPI's
  generated OpenAPI schema is the machine-readable source the frontend can check against.
- **Rationale:** one human-readable standard, per-feature contracts reviewed with the spec, and
  an automatically generated schema that can't drift from the code.
