"""format-on-write.sh, per specs/001-repo-foundations/contracts/claude-hooks.md (FR-010).

The hook formats only; linting stays with the lead's check-python.sh and check-frontend.sh.
"""

import json
import subprocess
from pathlib import Path

from conftest import run_hook as run_script


def run_hook(file_path: Path) -> subprocess.CompletedProcess[str]:
    """Feed a PostToolUse event for a just-written file to format-on-write.sh."""
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path)},
    }
    # Formatters may be fetched on first use (uvx, npx), so allow time.
    return run_script("format-on-write.sh", event, timeout=180)


def test_badly_formatted_python_is_reformatted(tmp_path: Path) -> None:
    """Fails if a written .py file is not formatted (Ruff)."""
    target = tmp_path / "messy.py"
    target.write_text("x = [1,2 ,3]\n", encoding="utf-8")

    result = run_hook(target)

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == "x = [1, 2, 3]\n"
    assert result.stdout == ""


def test_badly_formatted_typescript_is_reformatted(tmp_path: Path) -> None:
    """Fails if a written .ts file is not formatted (Prettier)."""
    target = tmp_path / "messy.ts"
    target.write_text("const a = {b:1}\n", encoding="utf-8")

    result = run_hook(target)

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == "const a = { b: 1 };\n"


def test_unparseable_file_is_kept_and_failure_reported(tmp_path: Path) -> None:
    """Fails if a syntax error loses the write or isn't reported back to Claude."""
    original = "def broken(:\n    pass\n"
    target = tmp_path / "broken.py"
    target.write_text(original, encoding="utf-8")

    result = run_hook(target)

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == original
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    assert "broken.py" in output["additionalContext"]


def test_other_file_types_are_left_alone(tmp_path: Path) -> None:
    """Fails if the hook touches files it shouldn't format (e.g. Markdown)."""
    original = "#  Title\n*  messy   list\n"
    target = tmp_path / "notes.md"
    target.write_text(original, encoding="utf-8")

    result = run_hook(target)

    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == original
    assert result.stdout == ""
