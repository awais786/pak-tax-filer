"""tax-rates-guard.sh, per specs/001-repo-foundations/contracts/claude-hooks.md (FR-008, FR-009).

Run: uv run --no-project --with pytest pytest .claude/hooks/tests
"""

import json
import subprocess

import pytest
from conftest import run_hook as run_script

REASON = (
    "Tax-rates module: rates must come from FBR's gazetted documents (constitution, Principle II). "
    "Approve only if this change cites its FBR source."
)


def run_hook(event: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """Feed one Claude Code PreToolUse event to tax-rates-guard.sh."""
    return run_script("tax-rates-guard.sh", event)


def edit_event(tool: str, file_path: str) -> dict[str, object]:
    """A PreToolUse event for a file-editing tool."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
    }


def bash_event(command: str) -> dict[str, object]:
    """A PreToolUse event for the Bash tool."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


INSIDE_PATHS = [
    "/home/dev/pak-tax-filer/backend/app/tax/rates/ty2026.py",
    "C:\\Users\\dev\\pak-tax-filer\\backend\\app\\tax\\rates\\ty2026.py",
    "C:/Users/dev/pak-tax-filer/backend/app/tax/rates/__init__.py",
]
OUTSIDE_PATHS = [
    "/home/dev/pak-tax-filer/backend/app/main.py",
    "/home/dev/pak-tax-filer/backend/app/tax/engine.py",
    # A name that merely starts with "rates" is not the guarded folder.
    "/home/dev/pak-tax-filer/backend/app/tax/ratesheet.py",
]


def assert_asks_with_fbr_reason(result: subprocess.CompletedProcess[str]) -> None:
    """The hook must ask (never deny) and give the contract's FBR reason."""
    assert result.returncode == 0
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "ask"
    assert output["permissionDecisionReason"] == REASON


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
@pytest.mark.parametrize("file_path", INSIDE_PATHS)
def test_editing_a_rates_file_asks(tool: str, file_path: str) -> None:
    """Fails if any edit inside backend/app/tax/rates/ goes through without a prompt."""
    assert_asks_with_fbr_reason(run_hook(edit_event(tool, file_path)))


@pytest.mark.parametrize(
    "command",
    [
        "sed -i 's/0.05/0.06/' backend/app/tax/rates/ty2026.py",
        "echo x > backend\\app\\tax\\rates\\ty2026.py",
    ],
)
def test_shell_command_touching_rates_asks(command: str) -> None:
    """Fails if a shell command naming the rates folder (either slash) runs without a prompt."""
    assert_asks_with_fbr_reason(run_hook(bash_event(command)))


@pytest.mark.parametrize("tool", ["Edit", "Write", "MultiEdit"])
@pytest.mark.parametrize("file_path", OUTSIDE_PATHS)
def test_editing_other_files_is_left_alone(tool: str, file_path: str) -> None:
    """Fails if the guard interferes with files outside the rates folder."""
    result = run_hook(edit_event(tool, file_path))
    assert result.returncode == 0
    assert result.stdout == ""


def test_other_shell_commands_are_left_alone() -> None:
    """Fails if the guard interferes with ordinary shell commands."""
    result = run_hook(bash_event("uv run pytest backend/tests"))
    assert result.returncode == 0
    assert result.stdout == ""
