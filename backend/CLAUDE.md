# Backend guide (FastAPI)

Loaded when working in `backend/`. The root `CLAUDE.md` and `.claude/rules/` still apply.

## Layout

- `app/main.py`: the FastAPI app; each area adds a router here (`app.include_router(...)`).
- `app/<area>/`: one package per area (e.g. `auth/`, `documents/`, `tax/`), holding `router.py`
  (HTTP only), `service.py` (logic as plain functions), `models.py` (SQLAlchemy) and schemas.
- `app/tax/rates/`: **guarded** (FBR sources only; the hook asks before any change).
- `alembic/versions/`: migrations, numbered `NNNN_<what>.py`.
- `tests/`: pytest; one file per behaviour area.

## Adding an endpoint

1. Write or update the feature's contract in `specs/NNN-*/contracts/` and follow
   `docs/api-conventions.md`.
2. Write the failing test in `tests/` with FastAPI's `TestClient`; run it and see it fail.
3. Add the route in `app/<area>/router.py`, keeping logic in `service.py`; money is `Decimal`.
4. Run `uv run pytest`, `uv run ruff format .`, `uv run pylint --recursive=y app alembic tests`,
   `uv run mypy app alembic tests` (the same checks as CI).

## Database and migrations

- Change models, then create a migration with the next number as its id, e.g.
  `docker compose exec backend alembic revision --autogenerate --rev-id 0002 -m "<what>"`
  (without `--rev-id` Alembic uses a random id); review it, then
  `docker compose exec backend alembic upgrade head`. Never edit the schema by hand.
- On a Linux host, files created inside the container (new migrations, `__pycache__`) are
  owned by root, because the container runs as root; `sudo chown` them or create migrations
  from the host with `uv run alembic ...` and a host `DATABASE_URL`. Windows and macOS are not
  affected.
- `DATABASE_URL` comes from the environment (docker-compose sets it); never put it in a file.
- Tests that need the database use a separate test database (set up in feature 002).

## Running tools on the host

`uv sync` here creates `backend/.venv` for editors and the lead's pylint hook. That hook only
looks for pylint in the repo-root `.venv` for now (proposed change: task T043); until then,
`uv tool install pylint` makes it available on the PATH.
