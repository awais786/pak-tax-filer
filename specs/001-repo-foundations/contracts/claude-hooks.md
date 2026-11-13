# Contract: Claude Code hooks and permissions

Added to the lead's existing `.claude/settings.json` (#10) **alongside** his hooks
(`git-safety.sh`, `check-python.sh`, `check-frontend.sh`), which are unchanged. Our scripts are
bash + `jq` in `.claude/hooks/`, like his; each reads Claude Code's JSON event from standard
input. (Amended 2026-11-04.)

## Hook scripts

| Script | Event | Owner |
|---|---|---|
| `git-safety.sh` | `PreToolUse` (Bash): asks on risky git operations | lead (#10) |
| `check-python.sh` | `PostToolUse`: pylint on written `.py` files | lead (#10) |
| `check-frontend.sh` | `PostToolUse`: the frontend's `lint` script | lead (#10) |
| `tax-rates-guard.sh` | `PreToolUse`: asks on tax-rates changes | 001 |
| `format-on-write.sh` | `PostToolUse`: Ruff / Prettier formatting | 001 |
| `contracts-gate.sh` | `Stop`: contract check for the branch's feature (issue #16) | 001 |

All six are tested by `pytest .claude/hooks/tests` with sample JSON inputs (CI hooks job).

## Tax-rates guard (`PreToolUse`, `tax-rates-guard.sh`)

- **Matches tools:** `Edit`, `Write`, `MultiEdit`, `Bash`.
- **Triggers when:** the tool's `file_path` is inside `backend/app/tax/rates/`, or a `Bash`
  `command` contains `rates` as a whole path segment (either slash direction), so reaching the
  folder in steps (`cd backend/app/tax && sed ... rates/ty2026.py`) still asks; names that only
  contain it (`test_rates.py`, `rates_for`) don't (amended 2026-11-12, review notes #39 item 3).
- **When triggered, outputs:**

  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "ask",
      "permissionDecisionReason": "Tax-rates module: rates must come from FBR's gazetted documents (constitution, Principle II). Approve only if this change cites its FBR source."
    }
  }
  ```

- **Otherwise:** exits 0 with no output (normal permission rules apply).
- **Never** returns `deny`: it asks, it does not block (spec FR-009).
- Covers spec FR-008, FR-009, User Story 2.

## Format-on-write (`PostToolUse`, `format-on-write.sh`)

- **Matches tools:** `Edit`, `Write`, `MultiEdit`.
- **Formats:** `.py` with Ruff; `.ts`, `.tsx`, `.js`, `.jsx`, `.css` with Prettier. Other files
  are left alone.
- **Formats only:** linting is done by the lead's `check-python.sh` and `check-frontend.sh`.
- **On formatter failure:** the file is kept as written; the error is reported back to Claude
  as `hookSpecificOutput.additionalContext`, the same way the lead's hooks report. The write
  itself is never undone.
- Covers spec FR-010.

## Permissions

| Rule | Actions |
|---|---|
| allow | pytest, Ruff, pylint, `npm test`/Vitest, `npm run lint`, Prettier, read-only git (`status`, `diff`, `log`, `show`, `branch`), `docker compose ps`/`logs` |
| ask | `git push`, `rm`, `git rm` |
| deny | reading `.env`, `.env.*` |

Anything not listed falls back to Claude Code's default of asking. Covers spec FR-011, FR-012.

## Contract gate (`Stop`, `contracts-gate.sh`; added for issue #16)

- **Feature:** from the branch name `NNN-…`; any other branch → exit 0, no output.
- **Runs:** `uv run --project backend python scripts/validate_contracts.py --feature NNN`.
- **Outputs:**

  | Check result | Feature state | Output |
  |---|---|---|
  | pass (exit 0) | any | none |
  | violations (exit 1) | unticked non-manual tasks remain | `{"systemMessage": "<violations>"}` |
  | violations (exit 1) | all non-manual tasks ticked | `{"decision": "block", "reason": "<violations>"}` |
  | setup error (exit 2) | any | `{"systemMessage": "Contract check could not run: <error>"}` |

- Never runs per edit. Covers spec FR-036, User Story 7.
