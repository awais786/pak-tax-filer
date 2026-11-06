# Python & FastAPI Conventions

- Follow PEP 8; keep functions small and single-purpose.
- Match whatever FastAPI app/project layout already exists once the backend
  is scaffolded — don't introduce a second convention alongside it.
- Keep business logic (especially the tax rules engine) out of routers/schemas:
  plain, unit-testable Python functions, versioned per tax year.
- Use Alembic migrations for every model change; never hand-edit the database schema.
- Prefer the standard library and already-declared dependencies over adding
  a new package for something a few lines of code can do.
- Type hints on new functions where the signature isn't obvious from context.
- Money is `Decimal`, never `float`, from the API boundary to the database.
- Use async SQLAlchemy sessions in request handlers; keep database access in services, not
  routers.
