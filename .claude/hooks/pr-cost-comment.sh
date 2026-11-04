#!/usr/bin/env bash
# SessionEnd hook: if the current branch has an open PR, post (or update) one
# comment on it with Claude Code token usage, accumulated across every session
# run against that PR. Never blocks or fails the session - exits 0 on any
# condition it can't handle (no PR yet, no gh, unreadable transcript, etc).
#
# Cost is an ESTIMATE at Anthropic's published list price (not the account's
# actual bill, which may differ with volume/enterprise pricing). Pricing table
# below is current as of 2026-11-04 - see https://platform.claude.com/docs/en/about-claude/pricing
# and update rate_for() in pr-cost-comment.jq when prices change. Unrecognized
# models price at $0 (under-reports cost rather than guessing).
set -uo pipefail

input=$(cat)
transcript_path=$(printf '%s' "$input" | jq -r '.transcript_path // empty')
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[[ -z "$cwd" ]] && cwd="$PWD"

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
jq_filter="$script_dir/pr-cost-comment.jq"

[[ -z "$transcript_path" || ! -f "$transcript_path" ]] && exit 0
[[ -f "$jq_filter" ]] || exit 0
command -v gh >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

pr_number=$(cd "$cwd" && gh pr view --json number -q .number 2>/dev/null)
[[ -z "$pr_number" ]] && exit 0

repo=$(cd "$cwd" && gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
[[ -z "$repo" ]] && exit 0

session_usage=$(jq -s -f "$jq_filter" "$transcript_path" 2>/dev/null)
[[ -z "$session_usage" || "$session_usage" == "[]" ]] && exit 0

marker_begin="<!--claude-code-usage"
marker_end="-->"

existing_url=$(cd "$cwd" && gh pr view "$pr_number" --json comments \
  --jq '([.comments[] | select(.body | contains("'"$marker_begin"'"))] | last | .url) // empty' 2>/dev/null)

old_totals='{"sessions":0,"models":[]}'
comment_id=""
if [[ -n "$existing_url" ]]; then
  comment_id="${existing_url##*issuecomment-}"
  old_body=$(cd "$cwd" && gh api "repos/$repo/issues/comments/$comment_id" --jq .body 2>/dev/null)
  extracted=$(printf '%s\n' "$old_body" | sed -n "/${marker_begin}/,/${marker_end}/p" | sed '1d;$d')
  if [[ -n "$extracted" ]] && printf '%s' "$extracted" | jq -e . >/dev/null 2>&1; then
    old_totals="$extracted"
  fi
fi

merged=$(jq -n --argjson old "$old_totals" --argjson new "$session_usage" '
  {
    sessions: (($old.sessions // 0) + 1),
    models: (
      ($old.models // []) + $new
      | group_by(.model)
      | map({
          model: .[0].model,
          input_tokens: (map(.input_tokens) | add),
          output_tokens: (map(.output_tokens) | add),
          cache_read_tokens: (map(.cache_read_tokens) | add),
          cache_creation_tokens: (map(.cache_creation_tokens) | add),
          cost_usd: (map(.cost_usd) | add)
        })
    )
  }
')

body=$(jq -r --argjson t "$merged" -n '
  def fmt_usd: (. * 100 | round) / 100 | tostring;
  ($t.models | map(.cost_usd) | add) as $total_cost
  | ($t.models | map(.input_tokens) | add) as $total_in
  | ($t.models | map(.output_tokens) | add) as $total_out
  | ($t.models | map(.cache_read_tokens) | add) as $total_cr
  | ($t.models | map(.cache_creation_tokens) | add) as $total_cc
  | "## Claude Code session usage (cumulative)\n\n"
  + "<!--claude-code-usage\n" + ($t | tostring) + "\n-->\n\n"
  + "| Sessions | Input tokens | Output tokens | Cache read | Cache write | Est. cost (list price) |\n"
  + "|---|---|---|---|---|---|\n"
  + "| \($t.sessions) | \($total_in) | \($total_out) | \($total_cr) | \($total_cc) | $\($total_cost | fmt_usd) |\n\n"
  + "_Estimate only, at Anthropic'"'"'s published list price - not this account'"'"'s actual bill. Per-model breakdown:_\n\n"
  + ($t.models | map("- `" + .model + "`: \(.input_tokens) in / \(.output_tokens) out - $\(.cost_usd | fmt_usd)") | join("\n"))
')

if [[ -n "$comment_id" ]]; then
  printf '%s' "$body" | jq -Rs '{body: .}' | (cd "$cwd" && gh api "repos/$repo/issues/comments/$comment_id" -X PATCH --input - >/dev/null 2>&1)
else
  printf '%s' "$body" | (cd "$cwd" && gh pr comment "$pr_number" --body-file - >/dev/null 2>&1)
fi

exit 0
