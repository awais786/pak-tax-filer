# PakTaxFiler — Engineering Rules

General-purpose rules for working in this repo. See the detailed rule files:

- @.claude/rules/security.md
- @.claude/rules/python-backend.md
- @.claude/rules/git-workflow.md
- @.claude/rules/testing-quality.md

## Summary

- Never commit or push API tokens, passwords, credentials, private keys, or
  other secrets.
- Never push directly to `main` or run a destructive Git operation
  (force-push, hard reset, history rewrite) without explicit approval.
- Never commit or push unless explicitly requested.
- Follow Python, Django, and whatever project conventions already exist in
  this repo — don't introduce a competing style.
- Prefer simple, maintainable implementations over clever ones.
- Don't overwrite existing user changes — check `git status`/`git diff`
  before touching files you didn't just create.
- Review the diff before considering any task complete.
- Run the appropriate tests and linters, and report the actual results —
  never an assumed outcome.

Project scope, MVP decisions, and the non-negotiables (deterministic tax
math, FBR-sourced rates, synthetic data only, planning-via-brainstorming)
are in `README.md` — read it before making product decisions.

## Project principles

The constitution (`.specify/memory/constitution.md`) overrides everything else. In one line each:

1. **Deterministic tax math:** every tax and reconciliation figure is plain code with `Decimal`, never an LLM.
2. **Authoritative sources only:** rates come from FBR's own gazetted documents, recorded with their source.
3. **Human confirmation before use:** AI-extracted values are used only after the user confirms them; the workflow stops for approval before calculating.
4. **Honest, labelled output:** "not yet practitioner-reviewed" on every report; the assistant always cites, or says it can't answer.
5. **Synthetic data only:** no real CNICs, NTNs, documents or salary records, anywhere.
6. **Test-first calculation, measured AI:** a failing test before the code; AI features have evals that CI enforces.
7. **MVP scope discipline:** nothing outside the approved specs; simplest design that meets them.

`backend/app/tax/rates/` is **guarded**: the tax-rates hook asks a human before any change there.

## Repo layout

- `backend/`: FastAPI app (`app/`), Alembic migrations (`alembic/`), tests (`tests/`); uv project.
- `frontend/`: React + TypeScript (Vite), tests next to components (`*.test.tsx`).
- `.claude/`: settings (hooks, permissions), rules, hooks and their tests (`hooks/tests/`).
- `specs/NNN-*/`: Spec Kit specs, plans, contracts and tasks, one folder per feature (001–008).
- `docs/superpowers/specs/`: brainstorming design docs.

## Commands

| What | Command |
|---|---|
| Start the app | `docker compose up -d` (backend :8000, frontend :5173) |
| Run migrations | `docker compose exec backend alembic upgrade head` |
| Backend tests | `docker compose exec backend pytest` |
| Frontend tests | `docker compose exec frontend npm test` |
| Hook tests (need bash and `jq`) | `uv run --no-project --with pytest pytest .claude/hooks/tests` |
| Lint | `uv run --project backend pylint --recursive=y backend/app backend/alembic backend/evals backend/tests`; `npm run lint` in `frontend/` |
| Format | `uv run --project backend ruff format backend`; `npx prettier --write src` in `frontend/` |
| Contract check | `uv run --project backend python scripts/validate_contracts.py --all` (or `--feature NNN`) |

## Conventions

| Use | When |
|---|---|
| `backend/CLAUDE.md`, `frontend/CLAUDE.md` | Loaded automatically when working in that folder |
| `.claude/rules/` (security, python-backend, git-workflow, testing-quality, architecture, frontend, api) | Always apply; `frontend.md` only under `frontend/` |
| `docs/api-conventions.md` | Designing or changing any endpoint |
| Skill `fastapi-feature` / `react-feature` | Building or changing a backend endpoint / frontend page |
| Skill `code-review` | Reviewing a diff or PR; it uses the subagents below |
| Subagents `backend-reviewer`, `frontend-reviewer` | Read-only review of `backend/` / `frontend/` changes |
| Spec Kit (`/speckit-*`) and `superpowers:brainstorming` | Planning a feature or non-trivial change (README "Planning process") |

## Contracts

- Run the contract check before calling a feature done; on a feature branch the `Stop` hook
  (`.claude/hooks/contracts-gate.sh`) runs it for you and blocks a finish while it fails with
  every task ticked. What it checks and how to read its messages: `docs/contracts.md`.
- A change to an endpoint, table or MCP tool updates the feature's contract (`*-api.md` and
  `api.yaml`, `data-model.md`, `mcp-tools.md`) in the same pull request. Never change a contract
  just to make the check pass.
- Before a feature's pull request, also run `/speckit-converge` and `/speckit-analyze`: the
  judgement review of the code against `spec.md`, `plan.md` and `tasks.md`, which the pass/fail
  check doesn't replace.

## Authentication and the taxpayer profile

- Protect every endpoint that touches a user's data with `current_user`
  (`app/auth/dependencies.py`): `user: Annotated[User, Depends(current_user)]`.
- Endpoints that need the tax year or ATL status use `require_profile`
  (`app/profile/dependencies.py`), which refuses users without a profile with `409`; to read it
  without refusing, use `get_profile`. Never add identity fields (name, CNIC, NTN) to the profile.
- State-changing endpoints depend on `require_json` (JSON only, research R3 of feature 002).
- Never log, return or store a password or session token; only their hashes are stored.
- Accounts: visitors sign up at `/signup` (`POST /api/auth/signup`, reusing `create_user`). For
  scripts: `docker compose exec backend python -m app.cli create-user --email demo@example.com`
  (prompts for the password twice).
- Extraction is limited to 10 per user and 100 for the app per 24 hours (feature 003 FR-017,
  `use_extraction` in `app/documents/service.py`); call it, then commit, before any new path
  that calls the AI for a document.
