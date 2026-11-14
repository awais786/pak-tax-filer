"""The engine and the calculator are plain arithmetic: no AI, database or network (feature 004,
T010; feature 010, T008; Principle I)."""

import ast
from pathlib import Path

import pytest

import app.tax

FORBIDDEN = ("anthropic", "google", "httpx", "httpx2", "sqlalchemy", "app.db", "app.tax.summary")


@pytest.mark.parametrize("module", ["engine", "calculator"])
def test_engine_imports_nothing_that_could_compute_a_figure_elsewhere(module: str) -> None:
    """Fails if engine.py or calculator.py imports an AI client, the database or the network
    (004 FR-007, 010 FR-003 and FR-007)."""
    source = Path(app.tax.__file__).with_name(f"{module}.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    for name in imported:
        assert not name.startswith(FORBIDDEN), name
