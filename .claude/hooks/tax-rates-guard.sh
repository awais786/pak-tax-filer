#!/usr/bin/env bash
# PreToolUse hook (Edit|Write|MultiEdit|Bash): any change to the tax-rates module pauses for
# human approval, because rates must come from FBR's gazetted documents (constitution,
# Principle II). It asks; it never blocks (spec FR-009). Contract:
# specs/001-repo-foundations/contracts/claude-hooks.md
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

# Compare with forward slashes so Windows paths (backslashes) match too.
file_path=${file_path//\\//}
command=${command//\\//}

# A command is guarded when "rates" appears in it as a whole path segment, not only as the full
# backend/app/tax/rates path: `cd backend/app/tax && sed -i ... rates/ty2026.py` reaches the folder
# in steps (review notes #39, item 3). Names that merely contain it (test_rates.py, rates_for,
# ratesheet.py) don't count. A false alarm only asks; it never blocks.
segment='(^|[^A-Za-z0-9_.-])rates(/|$|[^A-Za-z0-9_.-])'

guarded=false
if [[ -n "$file_path" && ( "$file_path" == */backend/app/tax/rates/* || "$file_path" == backend/app/tax/rates/* ) ]]; then
  guarded=true
elif [[ -n "$command" && "$command" =~ $segment ]]; then
  guarded=true
fi

if [[ "$guarded" == true ]]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: "Tax-rates module: rates must come from FBR'"'"'s gazetted documents (constitution, Principle II). Approve only if this change cites its FBR source."}}'
fi

exit 0
