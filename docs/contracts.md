# Contracts and the contract check

Each feature's spec promises things the code must keep: endpoints, tables, MCP tools. The
contract check (`scripts/validate_contracts.py`) compares those promises with the app and reports
every difference. It runs in three places: by hand, when Claude Code tries to finish a turn on a
feature branch (the `Stop` hook), and in CI on every pull request (the `contracts` job).

It catches drift that tests don't look for: an endpoint renamed in code but not in the spec, a
field dropped from a response, a column the data model lists but no model has, a new endpoint no
spec mentions. Whether the code does the *right thing* is still the tests' job, and whether it
does what the spec *means* is a review's (`/speckit-analyze`, `/speckit-converge`).

## Defining a contract

| What | Where | Checked |
|---|---|---|
| Endpoints | `specs/NNN-*/contracts/api.yaml` | Each operation exists, with its success status, required request fields and required response fields |
| Tables and columns | `specs/NNN-*/data-model.md`, tables headed `\| Column \| Type \|` under a `## table_name` heading | Each table and column exists in the SQLAlchemy models (a cell may list several, "`a`, `b`") |
| MCP tools | `specs/NNN-*/contracts/mcp-tools.md`, one `## tool_name` heading per tool | The MCP server lists exactly those tools |
| Tasks | `specs/NNN-*/tasks.md` | Once the last task is ticked, none is left unticked |

`api.yaml` is a small OpenAPI 3.1 file: the machine-checkable part of the feature's Markdown
contract (`*-api.md`), which stays the full contract. Change both together. Example:

```yaml
openapi: 3.1.0
info: {title: Feature 004 contract, version: 1.0.0}
paths:
  /api/tax/{tax_year}:
    get:
      responses:
        '200':
          description: success
          content:
            application/json:
              schema:
                type: object
                required: [tax_year, blocked_reason, salary_tax, label]
```

Only what the spec promises goes in: the success status and the required fields. Error statuses
are covered by each feature's API tests. Path parameter names don't matter (`{id}` and
`{document_id}` are the same endpoint).

For the response fields to be checked, the route must declare its response model (a Pydantic
return type, or `response_model=`), as `docs/api-conventions.md` requires; a route returning a
plain dict has no fields in the OpenAPI schema.

**Which features are checked:** only started ones (at least one ticked task). Tasks containing
`(manual)` (sign-offs, browser checks, requests to the lead) or `(Removed` are ignored: they never
count as left undone. Every app endpoint must appear in *some* feature's `api.yaml`, started or
not; FastAPI's own `/openapi.json`, `/docs` and `/redoc` are exempt.

## Running it

```bash
uv run --project backend python scripts/validate_contracts.py --all          # every feature
uv run --project backend python scripts/validate_contracts.py --feature 004  # one feature
uv run --project backend pytest scripts/tests                                # its own tests
```

It builds the app in memory (no server, no database), so it runs on the host. Exit codes: `0`
everything matches; `1` contract problems, one per line; `2` the check couldn't run (the app
can't be loaded, or a YAML file is invalid), which is never reported as a contract problem.

## Reading a failure

Each problem is one line: `[feature] file: item: problem`.

| Message | Meaning | Usual fix |
|---|---|---|
| `[004] contracts/api.yaml: GET /api/x: not in the app` | The contract promises an endpoint the app doesn't have (or has under another path or method) | Add or fix the route, or, if the spec changed, the contract |
| `... : no 201 response` | The route answers with another success status | Set `status_code=` on the route |
| `... : response field 'x' missing` / `request field 'x' missing` | The model lacks a field the contract requires | Add the field, or update the contract if the spec changed |
| `... : no response model declared, so its fields can't be checked` | The route returns a plain dict | Declare a response model |
| `[app] openapi: POST /api/x: in no feature's contracts/api.yaml` | An endpoint no spec mentions | Add it to the feature's Markdown contract and `api.yaml` |
| `[003] contracts/: api.yaml: missing (the feature has an API contract)` | A started feature has an `*-api.md` but no `api.yaml` | Write its `api.yaml` |
| `[007] data-model.md: t.c: column not in the models` (or `t: table not in the models`) | The data model promises a column or table the models lack | Add it with an Alembic migration, or fix the data model |
| `[006] contracts/mcp-tools.md: t: not listed by the MCP server` (or `listed by the MCP server, not in the contract`) | The tools and the contract differ | Add or remove the tool, or update the contract |
| `[008] tasks.md: T012: not ticked, but the feature's last task is` | A finished feature has a task left open | Do it and tick it, or mark it `(manual)` if only a person can |

Never change a contract just to make the check pass: if the code is wrong, fix the code. Change a
contract only when the spec itself changed, and say so in the pull request.

## The completion hook

On a branch named `NNN-…` (Spec Kit's convention), `.claude/hooks/contracts-gate.sh` runs the
check for feature NNN whenever Claude Code tries to finish a turn:

- the check passes: nothing;
- problems while the feature still has open tasks: shown in the session; work goes on;
- problems when every task is ticked: Claude Code is stopped from finishing and keeps fixing;
- the check can't run: shown, never blocking (a broken environment never traps a session).

It blocks at most once in a row, so a problem it can't fix never keeps a session going forever.
On other branches (`main`, `chore/…`) it does nothing.
