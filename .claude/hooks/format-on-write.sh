#!/usr/bin/env bash
# PostToolUse hook (Edit|Write|MultiEdit): format a just-written file. Formatting only; linting
# stays with the lead's check-python.sh and check-frontend.sh. Never undoes the write: if the
# formatter fails, the file is kept as written and the error is reported to Claude via
# additionalContext. Contract: specs/001-repo-foundations/contracts/claude-hooks.md
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_response.filePath // .tool_input.file_path // empty')

[[ -z "$file_path" ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

case "$file_path" in
  *.py)
    output=$(uvx ruff format "$file_path" 2>&1)
    ;;
  *.ts | *.tsx | *.js | *.jsx | *.css)
    output=$(npx --yes prettier --write "$file_path" 2>&1)
    ;;
  *)
    exit 0
    ;;
esac
status=$?

if [[ $status -ne 0 ]]; then
  jq -n --arg out "$output" --arg file "$file_path" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ("Formatting failed for " + $file + "; the file was kept as written:\n" + $out)}}'
fi

exit 0
