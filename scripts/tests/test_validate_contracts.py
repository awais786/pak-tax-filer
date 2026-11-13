"""validate_contracts.py, per specs/001-repo-foundations research R12 (task T071, issue #16).

A small sample FastAPI app and sample specs/ folders stand in for the real ones. Run:
uv run --project backend pytest scripts/tests
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_contracts as vc  # noqa: E402  # pylint: disable=wrong-import-position,import-error


class ItemIn(BaseModel):
    """A request body."""

    name: str
    note: str | None = None


class ItemOut(BaseModel):
    """A response body."""

    id: int
    name: str


def sample_app() -> dict[str, Any]:
    """The OpenAPI schema of a tiny app: two endpoints, one with no response model."""
    app = FastAPI()

    @app.post("/api/items", status_code=201)
    def create(item: ItemIn) -> ItemOut:
        return ItemOut(id=1, name=item.name)

    @app.get("/api/items/{item_id}")
    def read(item_id: int) -> ItemOut:
        return ItemOut(id=item_id, name="x")

    @app.get("/api/raw")
    def raw():  # type: ignore[no-untyped-def]  # deliberately no response model
        return {"value": 1}

    return app.openapi()


API_YAML = """\
openapi: 3.1.0
info: {title: t, version: '1'}
paths:
  /api/items:
    post:
      requestBody:
        content:
          application/json:
            schema: {type: object, required: [name]}
      responses:
        '201':
          description: created
          content:
            application/json:
              schema: {type: object, required: [id, name]}
  /api/items/{item_id}:
    get:
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema: {type: object, required: [id, name]}
  /api/raw:
    get:
      responses:
        '200': {description: ok}
"""

TASKS_STARTED = """\
- [x] T001 Do the first thing
- [ ] T002 Do the second thing
- [ ] T003 Run the checks
"""

DATA_MODEL = """\
# Data Model

## items

| Column | Type | Rules |
|---|---|---|
| `id` | integer | primary key |
| `name` | text | required |

## step_outputs (JSON)

| Key | Meaning |
|---|---|
| `anything` | not a table |
"""


def feature(  # pylint: disable=too-many-arguments  # each part of a feature folder
    specs: Path,
    name: str = "009-sample",
    *,
    api: str | None = API_YAML,
    tasks: str = TASKS_STARTED,
    data_model: str | None = None,
    mcp_tools: str | None = None,
) -> Path:
    """One sample feature folder."""
    folder = specs / name
    (folder / "contracts").mkdir(parents=True)
    (folder / "tasks.md").write_text(tasks, encoding="utf-8")
    if api is not None:
        (folder / "contracts" / "api.yaml").write_text(api, encoding="utf-8")
    if data_model is not None:
        (folder / "data-model.md").write_text(data_model, encoding="utf-8")
    if mcp_tools is not None:
        (folder / "contracts" / "mcp-tools.md").write_text(mcp_tools, encoding="utf-8")
    return folder


@pytest.fixture
def specs(tmp_path: Path) -> Path:
    """An empty specs/ folder."""
    folder = tmp_path / "specs"
    folder.mkdir()
    return folder


def check(specs: Path, **app: Any) -> list[str]:
    """Run the check on every feature with the sample app (or what the test passes)."""
    return vc.check_all(
        specs,
        openapi=app.get("openapi", sample_app()),
        tables=app.get("tables", {"items": {"id", "name"}}),
        mcp_tools=app.get("mcp_tools", set()),
    )


# ---- Endpoints ----


def test_everything_matching_passes(specs: Path) -> None:
    """Fails if a contract the app meets is reported."""
    feature(specs, data_model=DATA_MODEL)

    assert not check(specs)


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (
            ("/api/items/{item_id}:", "/api/things/{item_id}:"),
            "GET /api/things/{item_id}: not in the app",
        ),
        (("    post:", "    put:"), "PUT /api/items: not in the app"),
        (("'201':", "'202':"), "POST /api/items: no 202 response"),
        (
            ("required: [name]}", "required: [name, colour]}"),
            "POST /api/items: request field 'colour' missing",
        ),
        (
            ("required: [id, name]}", "required: [id, name, size]}"),
            "POST /api/items: response field 'size' missing",
        ),
    ],
    ids=["path", "method", "status", "request-field", "response-field"],
)
def test_a_contract_the_app_breaks_is_reported(
    specs: Path, change: tuple[str, str], problem: str
) -> None:
    """Fails if a missing path, method, status, request field or response field passes."""
    # Only the first match: the POST's schemas come first in API_YAML.
    feature(specs, api=API_YAML.replace(*change, 1))

    violations = check(specs)

    assert any(problem in v and v.startswith("[009] contracts/api.yaml: ") for v in violations), (
        violations
    )


def test_a_response_field_needs_a_declared_response_model(specs: Path) -> None:
    """Fails if a required response field passes for an endpoint with no response model."""
    feature(
        specs,
        api=API_YAML.replace(
            "        '200': {description: ok}",
            "        '200':\n          description: ok\n          content:\n"
            "            application/json:\n"
            "              schema: {type: object, required: [value]}",
        ),
    )

    violations = check(specs)

    assert any("GET /api/raw: no response model" in v for v in violations), violations


def test_an_endpoint_in_no_contract_is_reported(specs: Path) -> None:
    """Fails if the app has an endpoint that no feature's api.yaml lists."""
    feature(
        specs,
        api=API_YAML.replace(
            "  /api/raw:\n    get:\n      responses:\n        '200': {description: ok}\n",
            "",
        ),
    )

    violations = check(specs)

    assert violations == ["[app] openapi: GET /api/raw: in no feature's contracts/api.yaml"]


def test_the_docs_endpoints_need_no_contract(specs: Path) -> None:
    """Fails if FastAPI's own /openapi.json, /docs or /redoc are reported."""
    feature(specs)
    openapi = sample_app()
    openapi["paths"]["/docs"] = {"get": {"responses": {"200": {"description": "docs"}}}}

    assert not check(specs, openapi=openapi)


def test_a_started_feature_with_an_api_needs_an_api_yaml(specs: Path) -> None:
    """Fails if a started feature has an API contract in Markdown but no api.yaml."""
    folder = feature(specs, api=None)
    (folder / "contracts" / "items-api.md").write_text(
        "# Items API\n\nGET /api/items\n", encoding="utf-8"
    )
    feature(specs, "010-other")  # covers the endpoints

    violations = check(specs)

    assert "[009] contracts/: api.yaml: missing (the feature has an API contract)" in violations


def test_a_feature_with_no_ticked_task_is_skipped(specs: Path) -> None:
    """Fails if a feature nobody has started is checked against the app."""
    feature(
        specs,
        "010-later",
        api=API_YAML.replace("/api/raw", "/api/later"),
        tasks="- [ ] T001 Not started\n",
    )
    feature(specs)

    assert not check(specs)


# ---- Tables, tools and tasks ----


@pytest.mark.parametrize(
    ("tables", "problem"),
    [
        ({}, "items: table not in the models"),
        ({"items": {"id"}}, "items.name: column not in the models"),
    ],
)
def test_a_table_or_column_missing_from_the_models_is_reported(
    specs: Path, tables: dict[str, set[str]], problem: str
) -> None:
    """Fails if data-model.md promises a table or column the models don't have."""
    feature(specs, data_model=DATA_MODEL)

    violations = check(specs, tables=tables)

    assert f"[009] data-model.md: {problem}" in violations


def test_the_mcp_tools_must_equal_the_contracts_headings(specs: Path) -> None:
    """Fails if the MCP server lists a tool the contract doesn't name, or misses one."""
    mcp = (
        "# MCP tools\n\n## search\n\nFinds.\n\n## calculate\n\nWorks out.\n\n"
        "## .mcp.json\n\nSetup.\n"  # not a tool: its heading isn't snake_case
    )
    feature(specs, mcp_tools=mcp)

    assert not check(specs, mcp_tools={"search", "calculate"})
    violations = check(specs, mcp_tools={"search", "delete_everything"})
    assert "[009] contracts/mcp-tools.md: calculate: not listed by the MCP server" in violations
    assert (
        "[009] contracts/mcp-tools.md: delete_everything: "
        "listed by the MCP server, not in the contract" in violations
    )


def test_once_the_last_task_is_ticked_none_may_be_left(specs: Path) -> None:
    """Fails if a feature whose last task is ticked still has an unticked one."""
    feature(specs, tasks="- [x] T001 One\n- [ ] T002 Two\n- [x] T003 Run the checks\n")

    assert check(specs) == ["[009] tasks.md: T002: not ticked, but the feature's last task is"]


def test_mid_feature_unticked_tasks_are_fine(specs: Path) -> None:
    """Fails if a feature still in progress is reported for its open tasks."""
    feature(specs, tasks=TASKS_STARTED)

    assert not check(specs)


def test_manual_and_removed_tasks_are_ignored(specs: Path) -> None:
    """Fails if a human-only or removed task counts as left undone."""
    tasks = textwrap.dedent(
        """\
        - [x] T001 One
        - [ ] T002 (manual) Ask the lead
        - [ ] T003 [US3] (Removed 2026-11-12: no viewer)
        - [x] T004 Run the checks
        """
    )
    feature(specs, tasks=tasks)

    assert not check(specs)


# ---- The command ----


def test_invalid_yaml_is_a_setup_error(specs: Path) -> None:
    """Fails if an unreadable api.yaml is reported as a violation instead of a setup error."""
    feature(specs, api="paths: [unclosed\n")

    with pytest.raises(vc.SetupError):
        check(specs)


def test_the_command_exits_0_1_or_2(specs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails if the exit codes differ from 0 (pass), 1 (violations) and 2 (setup error)."""
    feature(specs, data_model=DATA_MODEL)
    app = {
        "openapi": sample_app(),
        "tables": {"items": {"id", "name"}},
        "mcp_tools": set(),
    }
    monkeypatch.setattr(vc, "load_app", lambda: app)

    assert vc.main(["--all", "--specs", str(specs)]) == 0
    assert vc.main(["--feature", "009", "--specs", str(specs)]) == 0
    app["tables"] = {}
    assert vc.main(["--all", "--specs", str(specs)]) == 1

    def broken() -> dict[str, Any]:
        raise vc.SetupError("the app can't be imported: boom")

    monkeypatch.setattr(vc, "load_app", broken)
    assert vc.main(["--all", "--specs", str(specs)]) == 2


def test_path_parameter_names_dont_matter(specs: Path) -> None:
    """Fails if `{id}` in a contract and `{item_id}` in the app count as different endpoints."""
    feature(specs, api=API_YAML.replace("/api/items/{item_id}:", "/api/items/{id}:"))

    assert not check(specs)


def test_a_plain_dict_response_is_no_response_model(specs: Path) -> None:
    """Fails if an endpoint returning a plain dict is reported field by field instead of once,
    as missing its response model."""
    openapi = sample_app()
    item = openapi["paths"]["/api/items/{item_id}"]["get"]["responses"]["200"]
    item["content"]["application/json"]["schema"] = {
        "type": "object",
        "additionalProperties": True,
    }
    feature(specs)

    violations = check(specs, openapi=openapi)

    assert violations == [
        "[009] contracts/api.yaml: GET /api/items/{item_id}: no response model declared, "
        "so its fields can't be checked"
    ]


def test_a_row_may_list_several_columns(specs: Path) -> None:
    """Fails if a data-model row naming two columns ("`a`, `b`") is read as one."""
    model = DATA_MODEL.replace("| `name` | text |", "| `name`, `size` | text |")
    feature(specs, data_model=model)

    assert check(specs, tables={"items": {"id", "name"}}) == [
        "[009] data-model.md: items.size: column not in the models"
    ]
