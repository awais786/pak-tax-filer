#!/usr/bin/env bash
# Stop hook: the contract check for the branch's feature, so a feature can't be called done while
# it fails (issue #16; specs/001-repo-foundations research R13). Contract:
# specs/001-repo-foundations/contracts/claude-hooks.md ("Contract gate").
#
#   check passes                       -> nothing
#   violations, tasks still open       -> {"systemMessage": ...}   (shown; work goes on)
#   violations, every task ticked      -> {"decision": "block", ...} (Claude keeps fixing)
#   the check can't run (exit 2)       -> {"systemMessage": ...}   (never blocks)
#
# It blocks at most once in a row: when Claude is already continuing because of this hook
# (stop_hook_active), a check still failing is shown instead, so it can never loop forever.
# Tests override CONTRACTS_BRANCH, CONTRACTS_ROOT and CONTRACTS_CHECK.
set -uo pipefail

input=$(cat)
continuing=$(printf '%s' "$input" | jq -r '.stop_hook_active // false')

root=${CONTRACTS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}
branch=${CONTRACTS_BRANCH:-$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null)}
[[ "$branch" =~ ^([0-9]{3})- ]] || exit 0
feature=${BASH_REMATCH[1]}

check=${CONTRACTS_CHECK:-uv run --project backend python scripts/validate_contracts.py}
out=$(mktemp)
err=$(mktemp)
trap 'rm -f "$out" "$err"' EXIT
(cd "$root" && OTEL_EXPORTER=none $check --feature "$feature") >"$out" 2>"$err"
status=$?

if [[ $status -eq 0 ]]; then
  exit 0
fi
if [[ $status -ne 1 ]]; then
  jq -cn --arg e "$(cat "$err" "$out" | tr -d '\r')" '{systemMessage: ("Contract check could not run: " + $e)}'
  exit 0
fi

violations=$(tr -d '\r' <"$out") # Windows Python ends its lines with \r\n

# Tasks that count: unticked, not (manual), not removed (as the check reads them).
open=$(cat "$root"/specs/"$feature"-*/tasks.md 2>/dev/null \
  | grep -E '^[[:space:]]*- \[ \] T[0-9]+' | grep -v '(manual)' | grep -c -v '(Removed')

if [[ $open -eq 0 && "$continuing" != "true" ]]; then
  jq -cn --arg v "$violations" \
    '{decision: "block", reason: ("Every task is ticked, but the contract check fails (docs/contracts.md):\n" + $v)}'
else
  jq -cn --arg v "$violations" '{systemMessage: ("Contract check (docs/contracts.md):\n" + $v)}'
fi
exit 0
