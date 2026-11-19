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
2. Write the failing test in `tests/`; run it and see it fail. Endpoint tests use the `client`
   fixture (`httpx2.AsyncClient` over `ASGITransport`), which shares the test's rolled-back
   async database session (feature 002, research R10). FastAPI's `TestClient` can't share that
   session, so it is only for endpoints that need no database, like `/health`.
3. Add the route in `app/<area>/router.py`, keeping logic in `service.py`; money is `Decimal`.
4. Run `uv run pytest`, `uv run ruff format .`, `uv run pylint --recursive=y app alembic evals tests`,
   `uv run mypy app alembic evals tests` (the same checks as CI).

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
- Tests that need the database ask for the `db` (rolled-back session) or `client` (HTTP client
  using that session) fixtures from `tests/conftest.py`; they run against `pak_tax_filer_test`,
  never development data, so run them in Docker: `docker compose exec backend pytest`.

## Running tools on the host

`uv sync` here creates `backend/.venv` for editors and the lead's pylint hook. That hook only
looks for pylint in the repo-root `.venv` for now (proposed change: task T043); until then,
`uv tool install pylint` makes it available on the PATH.

## Documents and extraction (feature 003)

- Other features read extracted figures **only** through
  `app.documents.service.confirmed_documents(db, user_id, tax_year)`: confirmed documents only
  (constitution, Principle III). Never query `extracted_fields` directly.
- Tests use `FakeExtractor` (fixture `fake_extractor`); no API key is needed. The real
  `GeminiExtractor` is tested through the SDK with an injected httpx2 `MockTransport`.
- Change the prompt (`extraction/prompt.py`), the schemas (`extraction/schemas.py`) or the
  normalisation and rules only together with an eval run, and paste its report in the PR:
  `python -m evals.extraction.generate`, then `python -m evals.extraction.run --model <model>`
  (needs `GEMINI_API_KEY`, free from AI Studio; contract: `specs/003-document-extraction/contracts/eval.md`).

## Tax engine (feature 004)

- Rates live **only** in `app/tax/rates/` (one module per tax year, e.g. `ty2026.py`), each
  value with its FBR source: document, location, Finance Act. The folder is guarded by a hook;
  call out every change in review. A new year is a new module in `RATES`; `engine.py` doesn't
  change.
- Every rate change comes with worked examples in `tests/tax/worked_examples.yaml`, hand-checked
  and signed off by a human (`signed_off_by`, `signed_off_date`); `test_sign_off.py` fails on an
  unsigned one.
- Tax figures are plain `Decimal` code with §219 rounding (`ROUND_HALF_UP`) on final amounts.
  Never compute, round or "check" a figure with an LLM. No AI summary (removed 2026-11-16, the
  lead: AI only where reasoning is needed): `tax_summary` in `app/tax/breakdown.py` writes the
  result's `summary` from its own amounts, never the two sides added together.
- Bank profit under s.7B is a final tax outside taxable income (s.8(1)(a)), in this engine as in
  the calculator: `taxable_income()` is the salary, so the 75% test and the Rs 10 million
  surcharge limit never depend on bank profit (amended 2026-11-17; the provisional
  `salary_share_ambiguous` and `surcharge_ambiguous` refusals were removed).
- Tests never call the real AI: the autouse `no_real_ai` fixture fakes the extractor and the
  assistant.

## Tax calculator (feature 010)

- `app/tax/calculator.py` is pure like the engine (import-linter and `test_engine_imports.py`
  guard it) and shares its rounding, steps and `band_for`; never a second engine. Typed amounts
  in, a result out; nothing stored or logged (`test_calculator_api.py` checks the database, logs
  and spans).
- The law it follows is in `specs/010-income-tax-engine/research.md`: rent is slab income after
  the one-fifth repairs allowance and counts in the 75% test; dividends and bank profit are final
  taxes outside taxable income (s.8(1)(a)). Its rules live in `ty2026.py` with printed and PDF
  page and `effective_from`.
- Its worked examples are `tests/tax/calculator_examples.yaml`, accepted provisionally (not hand
  checked): revise them, and the rules, when a tax practitioner reviews the app.

## Wealth statement (feature 005)

- `app/wealth/reconcile.py` stays pure: no database, network, clock or AI (an import test
  guards it). The formula is unreconciled = inflows - outflows - increase, with each step citing
  its SRO 1495(I)/2026 form line.
- Never compute, round or "check" a figure with an LLM, and never let one write the "where to
  look" lists (`app/wealth/breakdown.py`): they are fixed and contain no amounts. No AI
  summary (removed 2026-11-16): `wealth_summary` there writes the result's `summary` from its
  own amounts.
- Certificate figures come only from `confirmed_documents`, summed per type and then rounded
  (s.219) by `build_inputs`. Any change to the formula or the lines comes with signed-off worked
  examples in `tests/wealth/worked_examples.yaml` (`test_wealth_sign_off.py` fails if unsigned).
- The entries are stored; the result never is.

## RAG and MCP (feature 006)

- FBR source files are never committed: `python -m app.rag.build` downloads them into
  `data/corpus-cache/` (git- and docker-ignored) and checks each against its SHA-256 in
  `app/rag/sources.yaml` (FR-002).
- The corpus is fixed by the spec: adding or changing a source needs an approved spec change, a
  new SHA-256 in `sources.yaml`, and a retrieval eval run (`python -m evals.retrieval.run`;
  the CI job fails below `evals/retrieval/thresholds.yaml`).
- Never show an answer that skipped `app/rag/checks.py`: every citation a retrieved passage,
  every number (in digits, or a number phrase copied exactly) from a cited passage. The model
  never writes the refusal messages or the Tax page line; code does (`app/rag/service.py`).
- Tests use `FakeEmbedder` and `FakeAnswerer` (faked for every test by `no_real_ai`); the real
  Gemini classes are tested through the SDK with an httpx2 `MockTransport`.
- Only who asked and when is stored for a question (`ask_requests`, deleted after a day); never
  log the question text.
- MCP: the token comes only from `PAKTAX_TOKEN` in the developer's environment, never a file;
  tools call the app's own functions (search, 004's engine, 003's rules) and refuse an invalid
  token on every call. Setup: `docs/mcp.md`.

## Guided filing (feature 007)

- The gate is a backend rule: `app/workflow/service.py` returns a result only while the
  approval's fingerprint equals the inputs' current one (`state.result_allowed`); never add a
  path to the tax engine from the workflow that skips it. The result is recalculated, never
  stored.
- The steps are plain code, no AI (`app/workflow/steps.py`; amended 2026-11-16, the lead: only
  add AI where reasoning is needed): the document step lists what's confirmed and missing, the
  validation step runs 003's rules, the research step reads fixed Ordinance sections from 006's
  corpus. `test_the_run_needs_no_ai` fails if the run calls an AI. Raise `STEPS_VERSION` in
  `fingerprint.py` when the steps' output changes, so saved runs re-run once.
- Fingerprints and money read from the database compare amounts in one form (`1800000` and
  `1800000.00` are equal); tests that pass alone but fail in the full suite usually mean this.

## PDF export (feature 008)

- PDFs come only from `app/reports`: Jinja2 templates in `app/reports/templates/` rendered by
  WeasyPrint (`render.py`, in a thread). Every template extends `base.html`, whose running banner
  puts the practitioner label, "Demo data only." and the validation status
  (`app/reports/status.py`) on every page; never add a PDF that skips it (Principle IV).
- A PDF shows the same result as its screen, from the same functions; never AI-written text
  (summaries, agent notes). A blocked, not-ready or unapproved result exports nothing (`409`).
- Outside Docker (CI's runner), WeasyPrint needs Pango, HarfBuzz and a font: the packages are
  in `backend/Dockerfile` and installed by both backend CI jobs.

## Guardrails (feature 008)

- `.importlinter` keeps the AI out of the tax engine, the rates and the reconciliation;
  `tests/guardrails/` proves Principles I, III and IV across the app (its README lists what each
  file proves). CI's `guardrails` job runs both; run them with `uv run lint-imports` and
  `uv run pytest tests/guardrails`.

## Telemetry (feature 008)

- For developers only: spans go to the backend logs (`OTEL_EXPORTER=console`, the default;
  `none` silences them; tests default to `none`). There is no page for it in the app.
- Wrap every use of Gemini in `app.telemetry.ai.ai_call(feature, model)`, opened where the
  outcome is decided (around the call and the checks on its answer), and set `call.outcome`;
  use `record_refusal` when a limit stops a use before any call. A new Gemini client reports
  its tokens with `record_gemini_usage`.
- Never add an attribute that carries content (a prompt, a reply, a figure, an email, an id, a
  path with ids, SQL). `app/telemetry/setup.py` keeps only the attributes in `ALLOWED`; a new
  one needs a reason and goes in data-model.md, and `tests/telemetry/test_no_content.py` must
  still pass.
- Database spans come from `instrument_engine` (our own listener: the SQLAlchemy
  instrumentation doesn't support SQLAlchemy 2.1); a new engine should be wrapped with it.

## Admin area (feature 011)

- `app/admin/`: starlette-admin mounted at `/admin` by `site.build_admin` (from `app.main`, with a
  session factory built on first use, so importing the app needs no `DATABASE_URL`). Views are in
  `views.py`; logic is in plain functions: `overview.py` (dashboard counts, the account overview),
  `actions.py` (the four actions), `audit.py` (`record`, insert-only).
- Admin accounts are staff-only (`User.is_admin`, made only by `create-admin`, never by promoting
  an account): `User.can_use_app` keeps admin and disabled accounts out of the app's login,
  `current_user` and the MCP token check. Admins sign in with the app's sessions under an
  `admin_session` cookie (path `/admin`, 8 hours, SameSite=Strict) and their own throttle key.
- Every view is read-only with explicit fields (no create, edit, delete, export, import; no secret
  column). Viewing never changes data: a guided run is read as stored, never via
  `workflow.service.get_run`. Opening an account's details and each action write one audit entry.
- Actions never change figures or confirm documents (Principle III); deleting an account removes
  stored files first, and stops with nothing deleted if storage can't be reached.
- No AI in the admin area: `tests/guardrails/test_admin_no_ai.py` and the `no-ai-in-admin`
  import-linter contract. The library's logger is set to CRITICAL: it logs typed login emails.
- Admin tests use `admin_client` and `sign_in` from `tests/admin_helpers.py` (the admin on the
  test's rolled-back connection; form posts need the `csrftoken` from the page).

## Saved telemetry (feature 011)

- `app/telemetry/store.py`: an exporter (added through `add_exporter`, so behind `ALLOWED`)
  queues request and AI-call spans as rows of `telemetry_spans`; a writer in the app's lifespan
  saves them every 5 s with instrumentation suppressed (no database spans of its own), deletes
  rows older than 30 days, and never raises. `TELEMETRY_STORE=off` turns it off (tests and CI do).
