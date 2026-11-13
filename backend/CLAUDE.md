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
  Never compute, round or "check" a figure with an LLM. The AI summary (`tax/summary.py`) may
  only repeat breakdown numbers; plain code checks that and drops it otherwise.
- Tests never call the real AI: the autouse `no_real_ai` fixture fakes the extractor and the
  summariser; use `FakeSummariser` to test a summary.

## Wealth statement (feature 005)

- `app/wealth/reconcile.py` stays pure: no database, network, clock or AI (an import test
  guards it). The formula is unreconciled = inflows - outflows - increase, with each step citing
  its SRO 1495(I)/2026 form line.
- Never compute, round or "check" a figure with an LLM, and never let one write the "where to
  look" lists (`app/wealth/breakdown.py`): they are fixed and contain no amounts. The summary
  (`app/wealth/summary.py`) uses the shared `app.explain.number_check`, like the tax page's.
- Certificate figures come only from `confirmed_documents`, summed per type and then rounded
  (s.219) by `build_inputs`. Any change to the formula or the lines comes with signed-off worked
  examples in `tests/wealth/worked_examples.yaml` (`test_wealth_sign_off.py` fails if unsigned).
- The entries are stored; the result never is. A test's wealth summariser is faked by the
  autouse `no_real_ai` fixture.

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
- Agents get read-only tools only (`app/workflow/tools.py`; a test fails on anything else). Code
  decides each step's facts (what's missing, 003's rule issues, which passages exist); an agent
  only explains them, and its text is shown only after 004's number check or 006's citation
  checks. Otherwise the step shows its plain result (`fallback: true`).
- Each run of steps 1-3 counts as one question against 006's limits (`use_question`, committed
  before any AI is used); past a limit the steps use their plain results.
- Fingerprints and money read from the database compare amounts in one form (`1800000` and
  `1800000.00` are equal); tests that pass alone but fail in the full suite usually mean this.
- Tests use `FakeAgentClient` (faked for every test by `no_real_ai`); the real
  `GeminiAgentClient` is tested through the SDK with an httpx2 `MockTransport`.

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
