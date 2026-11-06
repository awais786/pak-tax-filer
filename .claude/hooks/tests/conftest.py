"""Shared helpers for the hook tests: run a hook script with a Claude Code event on stdin."""

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]


def bash() -> str:
    """Git Bash on Windows (plain `bash` there is WSL's), `bash` elsewhere.

    Claude Code runs hooks with Git Bash on Windows, so the tests do too.
    """
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            # git.exe sits in Git\cmd, Git\bin or Git\mingw64\bin; bash.exe is in Git\bin.
            for folder in Path(git).resolve().parents:
                candidate = folder / "bin" / "bash.exe"
                if candidate.exists():
                    return str(candidate)
        raise RuntimeError(
            "Git Bash not found; Claude Code on Windows needs Git for Windows."
        )
    return "bash"


def run_hook(
    script: str, event: Mapping[str, object], timeout: int = 10
) -> subprocess.CompletedProcess[str]:
    """Feed one Claude Code event to .claude/hooks/<script> on standard input."""
    return subprocess.run(
        [bash(), str(HOOKS_DIR / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
