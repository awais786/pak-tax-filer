---
name: "fastapi-feature"
description: "Add a backend feature slice to pak-tax-filer: contract, failing test, FastAPI route and service, migration, checks. Use when building or changing a backend endpoint."
---

# Add a FastAPI feature slice

Follow `backend/CLAUDE.md`, `.claude/rules/python-backend.md`, `.claude/rules/api.md` and the
constitution. Work on the feature's task in `specs/NNN-*/tasks.md`.

1. **Contract first.** Read (or update, in the same PR) the endpoint in
   `specs/NNN-*/contracts/`; it must follow `docs/api-conventions.md`.
2. **Failing test.** Write the test in `backend/tests/` with FastAPI's `TestClient`, asserting
   the contract's status, body and errors. Run `uv run pytest` and confirm it fails for the
   right reason (the behaviour is missing, not a typo or import path).
3. **Code.** Route in `app/<area>/router.py` (HTTP only), logic in `app/<area>/service.py` as
   plain functions, models in `app/<area>/models.py`. Money is `Decimal`. Never compute tax with
   an LLM (Principle I); never touch `app/tax/rates/` without FBR sources (Principle II).
4. **Migration** if models changed: `alembic revision --autogenerate -m "<what>"`, review the
   file, `alembic upgrade head`.
5. **Checks:** `uv run pytest`, `uv run ruff format .`, `uv run pylint app`, `uv run mypy app`.
   Report what actually ran and its result.
6. Tick the task in `tasks.md`, and show the diff for review before committing.
