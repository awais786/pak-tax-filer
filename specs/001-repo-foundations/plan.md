# Implementation Plan: Repo Foundations

**Branch**: `001-repo-foundations` | **Date**: 2026-11-03 (amended 2026-11-04) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-repo-foundations/spec.md`

## Summary

Create a runnable, empty three-service app (PostgreSQL + pgvector, FastAPI, React + TypeScript)
started by one Docker Compose command, plus a shared Claude Code setup built on the lead's #10
(root `CLAUDE.md`, rules, git-safety and lint hooks): a bash `PreToolUse` hook that asks for
approval on any change to `backend/app/tax/rates/`, a bash `PostToolUse` hook that formats
written files, and shared permissions, all added to his files rather than replacing them. Update the README's
setup section for FastAPI. For the lead's issues #4 and #5 (User Story 4): a GitHub Actions CI
workflow, backend and frontend `CLAUDE.md` files, topic rules, three skills, two review
subagents and a written API convention. Decisions and alternatives are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend, hooks), TypeScript on Node 26 LTS (frontend)

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2.0 (async) + asyncpg, Alembic; React,
Vite; dev: pytest, httpx2 (test client), Ruff (formatting only), pylint (linting, as in the lead's hook), mypy,
Vitest, React Testing Library, Prettier, oxlint (from the Vite template); CI: GitHub Actions

**Storage**: PostgreSQL 17 with pgvector (extension only; no tables in 001)

**Testing**: pytest (backend), Vitest (frontend), run inside containers per the README

**Target Platform**: local development via Docker Compose on Windows, macOS and Linux

**Project Type**: web application (backend + frontend)

**Performance Goals**: fresh clone to running app in under 10 minutes (SC-001)

**Constraints**: hooks in bash + `jq`, like the lead's (Git Bash on Windows); the lead's #10
files are extended, never replaced; one linter per language; no secrets needed; ports 8000 and
5173

**Scale/Scope**: skeleton only: one endpoint, one page, two hooks, one settings file, one CI
workflow, and the Claude Code conventions (2 folder guides; 3 new rules plus the lead's 4, one
renamed; 3 skills, 2 subagents)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | N/A | No calculations in 001 |
| II. Authoritative sources | PASS | Tax-rates path reserved and guarded from day one |
| III. Human confirmation | N/A | No extraction in 001 |
| IV. Honest output | N/A | No reports in 001 |
| V. Synthetic data only | PASS | No data of any kind |
| VI. Test-first, measured AI | PASS | Smoke tests for health and the placeholder page; CI runs every test on every PR |
| VII. MVP scope | PASS | README milestone 1 plus the lead's issues #4/#5; FR-014 excludes everything else |
| Stack | PASS | Exactly the constitution's stack. Libraries and tools inside it (uv, SQLAlchemy, Alembic, Vite, Ruff, pylint, oxlint, mypy, Prettier, pytest, Vitest, jq) and GitHub Actions (where the repo already lives) are not new stack components |
| Merge gates | PASS | CI created here, as constitution v1.2.1 requires; the eval gate is deferred to 003/006 |
| Secrets | PASS | Claude denied reading `.env`; no secrets needed |

**Post-design re-check:** PASS. The design adds no components beyond the stack and stores no
data.

## Project Structure

### Documentation (this feature)

```text
specs/001-repo-foundations/
├── plan.md              # This file
├── research.md          # Decisions R1–R10
├── data-model.md        # None for 001
├── quickstart.md        # Validation guide
├── contracts/
│   ├── health.md          # GET /health
│   ├── claude-hooks.md    # Hooks and permissions
│   └── api-conventions.md # API standard (published as docs/api-conventions.md)
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
docker-compose.yml          # db, backend, frontend
.env.example                # documented placeholders, no real values
CLAUDE.md                   # the lead's root guide (#10), extended (R9)
README.md                   # setup section updated for FastAPI
docs/api-conventions.md     # API standard (R10)

.github/workflows/ci.yml    # backend, frontend and hooks jobs (R8)

.claude/
├── settings.json           # the lead's hooks (#10) + ours + permissions
├── rules/                  # lead's: security, python-backend (renamed), git-workflow,
│                           #   testing-quality; new: architecture, frontend, api (R9)
├── skills/                 # + fastapi-feature, react-feature, code-review
├── agents/                 # backend-reviewer, frontend-reviewer
└── hooks/
    ├── git-safety.sh, check-python.sh, check-frontend.sh   # the lead's (#10), unchanged
    ├── tax-rates-guard.sh  # PreToolUse: ask on tax-rates changes
    ├── format-on-write.sh  # PostToolUse: Ruff / Prettier
    └── tests/              # pytest runs every hook with sample JSON (host and CI)

backend/
├── CLAUDE.md               # backend guide
├── Dockerfile
├── pyproject.toml          # uv-managed; Ruff format, pylint, mypy + pytest config
├── alembic.ini
├── alembic/versions/0001_enable_vector.py
├── app/
│   ├── main.py             # FastAPI app, GET /health
│   └── tax/rates/          # reserved for feature 004 (guarded)
└── tests/
    └── test_health.py

frontend/
├── CLAUDE.md               # frontend guide
├── Dockerfile
├── package.json            # npm test → vitest run; npm run lint → oxlint (Vite template's linter)
├── vite.config.ts
└── src/
    ├── App.tsx             # placeholder page
    └── App.test.tsx
```

**Structure Decision**: web application layout (`backend/` + `frontend/`), as the README's
three-service setup implies. Hooks run on the developer's machine, not in a container, so
their tests live beside them in `.claude/hooks/tests/` and run on the host
(`uv run --no-project --with pytest pytest .claude/hooks/tests`, needing bash and `jq`);
`CLAUDE.md` lists this command. Hook scripts use kebab-case `.sh` names to match the lead's.

## Complexity Tracking

No constitution violations; nothing to justify.
