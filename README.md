# PakTaxFiler

An open-source, hosted web app that helps a salaried Pakistani employee prepare
their income tax return and wealth statement — upload a salary certificate and
a bank profit certificate, get AI-assisted extraction you confirm yourself, a
deterministic tax calculation with a step-by-step explanation, a wealth
statement with reconciliation, and a RAG assistant that answers tax questions
with citations.

This repo is also a training project: the goal is for the engineer building it
to learn Django/DRF, React, and Claude Code itself — hooks, permissions, MCP,
RAG, and agentic workflows — by building something real, not a tutorial app.

**Status:** early build, synthetic data only, not yet reviewed by a tax
practitioner. Nothing in this app is tax advice until that changes.

## MVP scope

**In:**
- One taxpayer profile, one configurable tax year (TY2026).
- Two document types only: salary certificate, bank profit certificate.
- AI-assisted field extraction, with mandatory human confirmation before
  anything downstream uses the data.
- A deterministic tax calculation (salary income + profit on debt/§151) with
  a plain-language, step-by-step explanation.
- A wealth statement with deterministic reconciliation. An LLM may only
  explain a reconciliation result that's already been computed — it never
  computes the number itself.
- A RAG tax assistant, scoped to a small, named corpus (Income Tax Ordinance
  §12, §13, §149, §7B, §151; the Wealth Statement/Form 116 guide; the
  salaried-return/Form 114(1) guide). Always cites sources; says so
  explicitly when a question falls outside that corpus instead of guessing.
- A small MCP server exposing exactly three tools: `search_tax_documents`,
  `calculate_income_tax`, `validate_salary_information`.
- A simple agentic workflow (document → validate → research → calculate →
  explain → review) with a mandatory human-approval gate before calculation.

**Out (for now):** dividends, rental income, other income types; multiple
employers beyond a simple sum; IRIS login/auto-filing; any claim of
authoritative tax advice; real user documents (synthetic/demo data only
until a tax practitioner and legal review are in place).

## Non-negotiables

- **Tax and reconciliation math is deterministic code, never an LLM call.**
  Claude is only used for document extraction, the RAG assistant, and
  turning an already-computed number into a plain-language explanation.
- **Real FBR rates (brackets, §151 rates) must come from FBR's own gazetted
  documents** — not third-party calculator/blog sites, which were found to
  disagree with each other during planning.
- **Every exported report carries an explicit "not yet practitioner-reviewed"
  label**, unmissable, until that changes.
- **Synthetic/demo data only** until a tax practitioner and legal review are
  in place — no real user financial documents yet.

## Stack

Django + DRF, React + TypeScript, PostgreSQL + pgvector, Claude (API) for the
AI-specific pieces, Python MCP SDK, Docker Compose.

## Build order (milestones, not a task list — how to get there is up to you)

1. Repo foundations: Docker Compose skeleton, `CLAUDE.md`, Claude Code hooks
   (guard the tax-rates module, format-on-write) and permission settings.
2. Taxpayer profile + auth (Django/DRF + React).
3. Document upload + AI extraction (salary cert, bank profit cert) with
   confidence scoring and a human confirm/correct step. Extraction accuracy
   eval dataset.
4. Deterministic tax engine: real TY2026 rates sourced from FBR directly,
   salary + §151 calculation with explanation.
5. Wealth statement + deterministic reconciliation, with LLM explanation of
   the result only.
6. RAG knowledge base (bounded corpus, pgvector) + retrieval eval + MCP
   server (3 tools).
7. Agentic workflow wiring (document/validation/research agents, state
   machine, human-approval gate before calculation).
8. Telemetry, guardrail tests, CI (lint/type-check/te"sts + an eval-accuracy
   gate), PDF export with the validation-status banner.

## Planning process

Any new feature or non-trivial change in this repo should start with the
Claude Code `superpowers:brainstorming` skill, not straight into code: it
walks through intent, goals, non-goals, and constraints with you first and
produces a short design doc before anything gets built. This MVP plan itself
came out of that process. Keep using it going forward — save each design doc
under `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Turning an
approved design into actual implementation tasks/tests is left to whoever's
building it (see "Build order" above) — that part is intentionally not
pre-written here.

## Development setup

Prerequisites: Docker + Docker Compose, [`uv`](https://docs.astral.sh/uv/) (it provides
Python 3.13), Node 26+, and bash with `jq` (Git Bash on Windows; `winget install jqlang.jq`).

```bash
git clone git@github.com:awais786/pak-tax-filer.git
cd pak-tax-filer
docker compose up -d        # starts db (Postgres + pgvector), backend, frontend
docker compose exec backend alembic upgrade head
```

Create a demo user to log in with (synthetic data only; you're asked for the password twice):

```bash
docker compose exec backend python -m app.cli create-user --email demo@example.com
```

If you use Claude Code, also install the tools its hooks run on your machine:

```bash
(cd backend && uv sync)     # pylint, Ruff, mypy, pytest for the lint/format hooks
(cd frontend && npm ci)     # oxlint, Prettier for the frontend hooks
```

- Backend: `http://localhost:8000` · Frontend: `http://localhost:5173`
- Set `ANTHROPIC_API_KEY` in a local `.env` (not committed) before running
  anything that touches extraction, RAG, or the MCP server.
- Backend tests: `docker compose exec backend pytest`
- Frontend tests: `docker compose exec frontend npm test`
- Claude Code hook tests: `uv run --no-project --with pytest pytest .claude/hooks/tests`

## Full background

The original project proposal and the fuller design rationale (market
validation, scope decisions, what was cut and why) live in the lead's
planning notes and aren't duplicated here — ask if you need that context.
