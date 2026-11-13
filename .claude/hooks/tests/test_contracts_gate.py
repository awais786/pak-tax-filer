"""contracts-gate.sh, per specs/001-repo-foundations/contracts/claude-hooks.md (contract gate;
task T072, research R13, issue #16).

The real check is replaced by a stub that prints given lines and exits with a given code, so these
tests need no app. Run: uv run --no-project --with pytest pytest .claude/hooks/tests
"""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import run_hook

VIOLATION = "[009] contracts/api.yaml: GET /api/items: not in the app"
OPEN_TASKS = "- [x] T001 One\n- [ ] T002 Two\n- [ ] T003 (manual) Ask the lead\n"
ALL_TICKED = "- [x] T001 One\n- [x] T002 Two\n- [ ] T003 (manual) Ask the lead\n"


def gate(
    tmp_path: Path,
    *,
    branch: str = "009-sample",
    tasks: str = OPEN_TASKS,
    exit_code: int = 1,
    output: str = VIOLATION,
    continuing: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the gate on a sample repo whose check is a stub."""
    (tmp_path / "specs" / "009-sample").mkdir(parents=True)
    (tmp_path / "specs" / "009-sample" / "tasks.md").write_text(tasks, encoding="utf-8")
    stub = tmp_path / "check.sh"
    stream = ">&2" if exit_code == 2 else ""
    # A heredoc prints the text as it is, apostrophes and all.
    stub.write_text(
        f"cat {stream} <<'TEXT'\n{output}\nTEXT\nexit {exit_code}\n", encoding="utf-8"
    )
    event = {"hook_event_name": "Stop", "stop_hook_active": continuing}
    return run_hook(
        "contracts-gate.sh",
        event,
        timeout=20,
        env={
            "CONTRACTS_BRANCH": branch,
            "CONTRACTS_ROOT": str(tmp_path),
            "CONTRACTS_CHECK": f"bash {stub.as_posix()}",
        },
    )


def test_a_branch_that_isnt_a_feature_is_left_alone(tmp_path: Path) -> None:
    """Fails if the gate runs, or says anything, off a feature branch (e.g. main)."""
    result = gate(tmp_path, branch="main")

    assert result.returncode == 0 and result.stdout == ""


def test_a_passing_check_says_nothing(tmp_path: Path) -> None:
    """Fails if a passing check produces any output."""
    result = gate(tmp_path, exit_code=0, output="")

    assert result.returncode == 0 and result.stdout == ""


def test_violations_mid_feature_are_shown_without_blocking(tmp_path: Path) -> None:
    """Fails if work in progress is blocked, or its violations aren't shown."""
    result = gate(tmp_path, tasks=OPEN_TASKS)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "decision" not in output
    assert VIOLATION in output["systemMessage"]


def test_violations_with_every_task_ticked_block(tmp_path: Path) -> None:
    """Fails if a feature can be called done (every non-manual task ticked) while its contract
    check fails."""
    result = gate(tmp_path, tasks=ALL_TICKED)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["decision"] == "block"
    assert VIOLATION in output["reason"]


def test_a_check_that_cannot_run_never_blocks(tmp_path: Path) -> None:
    """Fails if a broken environment (the check exits 2) blocks the session."""
    result = gate(
        tmp_path, tasks=ALL_TICKED, exit_code=2, output="the app can't be loaded"
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "decision" not in output
    assert output["systemMessage"].startswith("Contract check could not run:")
    assert "the app can't be loaded" in output["systemMessage"]


def test_it_blocks_only_once_in_a_row(tmp_path: Path) -> None:
    """Fails if a check still failing after one block blocks again, which would keep the
    session going forever (Claude Code's stop_hook_active)."""
    result = gate(tmp_path, tasks=ALL_TICKED, continuing=True)

    output = json.loads(result.stdout)
    assert "decision" not in output
    assert VIOLATION in output["systemMessage"]


@pytest.mark.parametrize("tasks", [OPEN_TASKS, ALL_TICKED])
def test_the_output_is_one_json_object(tmp_path: Path, tasks: str) -> None:
    """Fails if anything besides the JSON reaches standard output (Claude Code reads it)."""
    result = gate(tmp_path, tasks=tasks)

    assert result.stdout.count("\n") <= 1
    json.loads(result.stdout)
