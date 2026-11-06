"""The lead's hooks from #10 (git-safety.sh, check-python.sh, check-frontend.sh).

Tests only (2026-11-04 clarification): his scripts are not changed here.
"""

import json

import pytest
from conftest import run_hook


def bash_event(command: str) -> dict[str, object]:
    """A PreToolUse event for the Bash tool."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def write_event(file_path: str) -> dict[str, object]:
    """A PostToolUse event for a written file."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "tool_response": {"filePath": file_path},
    }


@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin feature",
        "git push origin main",
        "git reset --hard HEAD~1",
    ],
)
def test_git_safety_asks_on_risky_git(command: str) -> None:
    """Fails if a force-push, push to main or hard reset can run without a prompt."""
    result = run_hook("git-safety.sh", bash_event(command))
    assert result.returncode == 0
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "ask"


@pytest.mark.parametrize("command", ["git status", "git diff", "uv run pytest"])
def test_git_safety_stays_silent_on_safe_commands(command: str) -> None:
    """Fails if ordinary commands get a git-safety prompt."""
    result = run_hook("git-safety.sh", bash_event(command))
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "file_path", ["README.md", "frontend/src/App.tsx", "notes.txt"]
)
def test_check_python_ignores_non_python_files(file_path: str) -> None:
    """Fails if the pylint hook reacts to files that aren't .py."""
    result = run_hook("check-python.sh", write_event(file_path))
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "file_path", ["README.md", "backend/app/main.py", "styles.css"]
)
def test_check_frontend_ignores_non_script_files(file_path: str) -> None:
    """Fails if the frontend lint hook reacts to files that aren't .js/.jsx/.ts/.tsx/.vue."""
    result = run_hook("check-frontend.sh", write_event(file_path))
    assert result.returncode == 0
    assert result.stdout == ""
