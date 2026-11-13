"""The contract check (feature 001, User Story 7; research R12, issue #16).

Compares what each feature's spec promises with what the app has, for every started feature (at
least one ticked task in its tasks.md):

- each operation in `contracts/api.yaml` exists in the app's OpenAPI schema, with its success
  status, required request fields and required response fields (response fields need a declared
  response model);
- no app operation is missing from every feature's api.yaml (FastAPI's docs pages aside);
- a started feature with an API contract in Markdown has an api.yaml;
- each table and column in `data-model.md` tables headed `| Column | Type |` exists in the models;
- the MCP server lists exactly the tools named by `contracts/mcp-tools.md`'s snake_case headings;
- once a feature's last task is ticked, none is left unticked (`(manual)` and removed tasks are
  ignored).

Usage: `uv run --project backend python scripts/validate_contracts.py --all` (or
`--feature NNN`). Exit 0: pass; 1: violations, one per line as `[NNN] file: item: problem`;
2: the check couldn't run (the app can't be imported, a YAML file is invalid). docs/contracts.md
explains each message.
"""

import argparse
import importlib
import asyncio
import re
import sys
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("get", "put", "post", "delete", "patch", "options", "head")
# FastAPI's own pages; no feature promises them.
DOCS_PATHS = frozenset({"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"})
TASK = re.compile(r"^\s*- \[(?P<done>[ xX])\] (?P<id>T\d+)\b(?P<rest>.*)$")
TOOL_HEADING = re.compile(r"^## ([a-z][a-z0-9_]*)\s*$")


class SetupError(Exception):
    """The check couldn't run (exit 2)."""


# ---- Reading a feature ----


def tasks_of(folder: Path) -> list[tuple[str, bool]]:
    """(task id, ticked) for each task that counts: not `(manual)`, not removed."""
    path = folder / "tasks.md"
    if not path.exists():
        return []
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TASK.match(line)
        if match is None:
            continue
        rest = match["rest"]
        if "(manual)" in rest or "(Removed" in rest:
            continue
        tasks.append((match["id"], match["done"] != " "))
    return tasks


def started(folder: Path) -> bool:
    """At least one task is ticked (a feature not started yet isn't checked)."""
    return any(done for _, done in tasks_of(folder))


def unfinished(folder: Path) -> list[str]:
    """The unticked tasks that count (the completion hook blocks once there are none)."""
    return [task for task, done in tasks_of(folder) if not done]


def _yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SetupError(f"{path.relative_to(path.parents[2])}: invalid YAML ({exc})") from exc


def contract_operations(folder: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """(METHOD, path) -> the operation, from the feature's api.yaml (none if it has none)."""
    path = folder / "contracts" / "api.yaml"
    if not path.exists():
        return {}
    paths = _yaml(path).get("paths") or {}
    if not isinstance(paths, dict):
        raise SetupError(f"{folder.name}/contracts/api.yaml: `paths` isn't a mapping")
    return {
        (method.upper(), route): operation or {}
        for route, item in paths.items()
        for method, operation in (item or {}).items()
        if method in METHODS
    }


def data_model_tables(folder: Path) -> dict[str, list[str]]:
    """table -> columns, from data-model.md's tables headed `| Column | Type |`, each named by
    the `## heading` above it."""
    path = folder / "data-model.md"
    if not path.exists():
        return {}
    tables: dict[str, list[str]] = {}
    heading = ""
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            heading = line[3:].split()[0].strip("`") if line[3:].split() else ""
            in_table = False
        elif re.match(r"^\|\s*Column\s*\|\s*Type\s*\|", line):
            in_table = True
            tables.setdefault(heading, [])
        elif in_table and line.startswith("|"):
            first = line.strip("|").split("|")[0]
            for column in (c.strip().strip("`") for c in first.split(",")):
                if column and not set(column) <= set("-: "):
                    tables[heading].append(column)
        else:
            in_table = False
    return tables


def mcp_tool_names(folder: Path) -> set[str] | None:
    """The tools contracts/mcp-tools.md names (its snake_case `## headings`), or None."""
    path = folder / "contracts" / "mcp-tools.md"
    if not path.exists():
        return None
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TOOL_HEADING.match(line)
        if match:
            names.add(match[1])
    return names


def shape(route: str) -> str:
    """A path with its parameter names dropped: `/api/documents/{id}` and
    `/api/documents/{document_id}` are the same endpoint."""
    return re.sub(r"{[^}]*}", "{}", route)


def features(specs: Path) -> list[Path]:
    """The feature folders (`NNN-name`), in order."""
    return sorted(p for p in specs.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))


# ---- The app's schema ----


def _resolve(schema: dict[str, Any], openapi: dict[str, Any]) -> dict[str, Any]:
    """A schema with its `$ref`s followed and `allOf` merged (enough to read its fields)."""
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = openapi.get("components", {}).get("schemas", {}).get(name, {})
    if "allOf" in schema:
        merged: dict[str, Any] = {"properties": {}}
        for part in schema["allOf"]:
            merged["properties"].update(_resolve(part, openapi).get("properties", {}))
        return merged
    return schema


def _fields(body: dict[str, Any] | None, openapi: dict[str, Any]) -> set[str] | None:
    """The JSON fields a request or response body has, or None if it declares no schema."""
    content = (body or {}).get("content", {})
    schema = content.get("application/json", {}).get("schema")
    properties = _resolve(schema, openapi).get("properties") if schema else None
    # No named fields (e.g. a route returning a plain dict) means no response model.
    return set(properties) if properties else None


def _required(body: dict[str, Any] | None) -> list[str]:
    content = (body or {}).get("content", {})
    return list(content.get("application/json", {}).get("schema", {}).get("required", []))


# ---- The checks ----


def check_feature(
    folder: Path,
    openapi: dict[str, Any],
    tables: dict[str, set[str]],
    mcp_tools: set[str],
) -> list[str]:
    """Every problem with one started feature, as `[NNN] file: item: problem`."""
    tag = f"[{folder.name[:3]}]"
    return [
        *_check_api_yaml_exists(tag, folder),
        *(
            problem
            for (method, route), promised in contract_operations(folder).items()
            for problem in _check_operation(tag, method, route, promised, openapi)
        ),
        *_check_tables(tag, folder, tables),
        *_check_tools(tag, folder, mcp_tools),
        *_check_tasks(tag, folder),
    ]


def _check_api_yaml_exists(tag: str, folder: Path) -> list[str]:
    contracts = folder / "contracts"
    has_api_md = contracts.exists() and any(p.name.endswith("api.md") for p in contracts.iterdir())
    if has_api_md and not (contracts / "api.yaml").exists():
        return [f"{tag} contracts/: api.yaml: missing (the feature has an API contract)"]
    return []


def _check_tables(tag: str, folder: Path, tables: dict[str, set[str]]) -> list[str]:
    found = []
    for table, columns in data_model_tables(folder).items():
        if table not in tables:
            found.append(f"{tag} data-model.md: {table}: table not in the models")
            continue
        found += [
            f"{tag} data-model.md: {table}.{column}: column not in the models"
            for column in columns
            if column not in tables[table]
        ]
    return found


def _check_tools(tag: str, folder: Path, mcp_tools: set[str]) -> list[str]:
    named = mcp_tool_names(folder)
    if named is None:
        return []
    where = f"{tag} contracts/mcp-tools.md"
    return [
        *(f"{where}: {tool}: not listed by the MCP server" for tool in sorted(named - mcp_tools)),
        *(
            f"{where}: {tool}: listed by the MCP server, not in the contract"
            for tool in sorted(mcp_tools - named)
        ),
    ]


def _check_tasks(tag: str, folder: Path) -> list[str]:
    tasks = tasks_of(folder)
    if not tasks or not tasks[-1][1]:  # not finished: open tasks are fine
        return []
    return [
        f"{tag} tasks.md: {task}: not ticked, but the feature's last task is"
        for task, done in tasks
        if not done
    ]


def _check_operation(
    tag: str, method: str, route: str, promised: dict[str, Any], openapi: dict[str, Any]
) -> list[str]:
    where = f"{tag} contracts/api.yaml: {method} {route}"
    paths = {shape(r): item for r, item in openapi.get("paths", {}).items()}
    actual = paths.get(shape(route), {}).get(method.lower())
    if actual is None:
        return [f"{where}: not in the app"]
    found = []
    promised_responses = promised.get("responses") or {}
    for status in (s for s in promised_responses if str(s).startswith("2")):
        if str(status) not in actual.get("responses", {}):
            found.append(f"{where}: no {status} response")
            continue
        wanted = _required(promised_responses[status])
        if not wanted:
            continue
        has = _fields(actual["responses"][str(status)], openapi)
        if has is None:
            found.append(f"{where}: no response model declared, so its fields can't be checked")
        else:
            found += [f"{where}: response field '{f}' missing" for f in wanted if f not in has]
    wanted = _required(promised.get("requestBody"))
    if wanted:
        has = _fields(actual.get("requestBody"), openapi) or set()
        found += [f"{where}: request field '{f}' missing" for f in wanted if f not in has]
    return found


def uncovered(folders: Sequence[Path], openapi: dict[str, Any]) -> list[str]:
    """App operations no feature's api.yaml lists."""
    promised = {
        (method, shape(route))
        for folder in folders
        for method, route in contract_operations(folder)
    }
    return [
        f"[app] openapi: {method.upper()} {route}: in no feature's contracts/api.yaml"
        for route, item in sorted(openapi.get("paths", {}).items())
        if route not in DOCS_PATHS
        for method in item
        if method in METHODS and (method.upper(), shape(route)) not in promised
    ]


def check_all(
    specs: Path,
    *,
    openapi: dict[str, Any],
    tables: dict[str, set[str]],
    mcp_tools: set[str],
    only: str | None = None,
) -> list[str]:
    """Every problem: each started feature's (or only feature `only`'s), then the app's."""
    folders = features(specs)
    found: list[str] = []
    for folder in folders:
        if only is not None and not folder.name.startswith(f"{only}-"):
            continue
        if started(folder):
            found += check_feature(folder, openapi, tables, mcp_tools)
    return found + uncovered(folders, openapi)


# ---- The real app ----


def load_app() -> dict[str, Any]:
    """The real app's OpenAPI schema, tables and MCP tools, built in-process (no server)."""
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        # pylint: disable=import-outside-toplevel,import-error  # backend/ is put on the path above
        from app.db import Base
        from app.main import app as fastapi_app
        from app.mcp_server.server import build_server
        from app.rag.embed import FakeEmbedder

        # Each models module registers its tables on Base.metadata (as alembic/env.py does).
        for area in (
            "auth",
            "documents",
            "profile",
            "rag",
            "tokens",
            "wealth",
            "workflow",
        ):
            importlib.import_module(f"app.{area}.models")
        tables = {name: set(table.columns.keys()) for name, table in Base.metadata.tables.items()}
        return {
            "openapi": fastapi_app.openapi(),
            "tables": tables,
            "mcp_tools": asyncio.run(_mcp_tools(build_server, FakeEmbedder())),
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Anything that stops the app loading is a setup error (exit 2), never a violation.
        raise SetupError(f"the app can't be loaded: {type(exc).__name__}: {exc}") from exc


async def _mcp_tools(build_server: Any, embedder: Any) -> set[str]:
    from mcp import Client  # pylint: disable=import-outside-toplevel

    @asynccontextmanager
    async def no_sessions() -> AsyncIterator[None]:  # listing tools opens none
        yield None

    async with Client(build_server(None, no_sessions, embedder)) as client:
        listed = await client.list_tools()
    return {tool.name for tool in listed.tools}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check; the exit code says how it went."""
    parser = argparse.ArgumentParser(description="Check the app against the specs' contracts.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--all", action="store_true", help="every started feature")
    which.add_argument("--feature", metavar="NNN", help="one feature, e.g. 004")
    parser.add_argument("--specs", type=Path, default=ROOT / "specs", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        app = load_app()
        found = check_all(args.specs, only=args.feature, **app)
    except SetupError as exc:
        print(f"Contract check could not run: {exc}", file=sys.stderr)
        return 2
    for line in found:
        print(line)
    if found:
        print(f"{len(found)} contract problem(s); see docs/contracts.md.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
