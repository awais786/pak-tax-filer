#!/usr/bin/env bash
# Tests for pr-cost-comment.sh, using a fake `gh` so no network/GitHub calls happen.
# Run: bash .claude/hooks/tests/test_pr_cost_comment.sh
set -uo pipefail

hooks_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fail=0
assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" != "$actual" ]]; then
    echo "FAIL: $desc"
    echo "  expected: $expected"
    echo "  actual:   $actual"
    fail=1
  else
    echo "ok: $desc"
  fi
}

mkdir -p "$work/bin" "$work/state"

# A fake `gh` covering exactly the calls pr-cost-comment.sh makes.
cat > "$work/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
set -u
state_dir="__STATE_DIR__"
args="$*"

if [[ "$args" == "pr view --json number -q .number" ]]; then
  [[ -f "$state_dir/no_pr" ]] && exit 1
  echo "42"

elif [[ "$args" == "repo view --json nameWithOwner -q .nameWithOwner" ]]; then
  echo "testowner/testrepo"

elif [[ "$args" == "pr view 42 --json comments --jq"* ]]; then
  [[ -f "$state_dir/comment_url.txt" ]] && cat "$state_dir/comment_url.txt" || echo ""

elif [[ "$args" == "api repos/testowner/testrepo/issues/comments/1001 --jq .body" ]]; then
  cat "$state_dir/comment_body.txt"

elif [[ "$args" == "api repos/testowner/testrepo/issues/comments/1001 -X PATCH --input -" ]]; then
  jq -r .body > "$state_dir/comment_body.txt"

elif [[ "$args" == "pr comment 42 --body-file -" ]]; then
  cat > "$state_dir/comment_body.txt"
  echo "https://github.com/testowner/testrepo/pull/42#issuecomment-1001" > "$state_dir/comment_url.txt"

else
  echo "UNHANDLED: gh $*" >> "$state_dir/unhandled.log"
fi
GHEOF
sed -i '' "s|__STATE_DIR__|$work/state|" "$work/bin/gh"
chmod +x "$work/bin/gh"

run_hook() {
  local transcript="$1"
  jq -n --arg t "$transcript" --arg c "$PWD" '{transcript_path:$t, cwd:$c}' \
    | PATH="$work/bin:$PATH" bash "$hooks_dir/pr-cost-comment.sh"
}

# --- Fixture: one session with two models, cache read + cache write on one entry ---
cat > "$work/transcript.jsonl" <<'EOF'
{"type":"user","message":{"role":"user","content":"hi"}}
{"type":"assistant","message":{"role":"assistant","model":"claude-sonnet-5-5","content":[],"usage":{"input_tokens":1000,"output_tokens":500,"cache_read_input_tokens":200,"cache_creation_input_tokens":100}}}
{"type":"assistant","message":{"role":"assistant","model":"claude-sonnet-5-5","content":[],"usage":{"input_tokens":2000,"output_tokens":1000,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
{"type":"assistant","message":{"role":"assistant","model":"claude-haiku-5-5","content":[],"usage":{"input_tokens":500,"output_tokens":100,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}}}
EOF

# Test 1: no PR on the branch -> exits 0, no comment created
touch "$work/state/no_pr"
run_hook "$work/transcript.jsonl"
assert_eq "no PR: no comment file created" "false" "$([[ -f "$work/state/comment_body.txt" ]] && echo true || echo false)"
rm -f "$work/state/no_pr"

# Test 2: empty/no-usage transcript -> exits 0, no comment created
echo '{"type":"user","message":{"role":"user","content":"hi"}}' > "$work/empty.jsonl"
run_hook "$work/empty.jsonl"
assert_eq "empty transcript: no comment file created" "false" "$([[ -f "$work/state/comment_body.txt" ]] && echo true || echo false)"

# Test 3: first real session creates a comment with correct totals and cost
run_hook "$work/transcript.jsonl"
body=$(cat "$work/state/comment_body.txt")
marker=$(printf '%s\n' "$body" | sed -n '/<!--claude-code-usage/,/-->/p' | sed '1d;$d')
assert_eq "session 1: sessions count" "1" "$(printf '%s' "$marker" | jq -r .sessions)"
assert_eq "session 1: total input tokens" "3500" "$(printf '%s' "$marker" | jq '[.models[].input_tokens] | add')"
assert_eq "session 1: total output tokens" "1600" "$(printf '%s' "$marker" | jq '[.models[].output_tokens] | add')"
# sonnet: 3000/1e6*2 + 1500/1e6*10 + 100/1e6*2.50 + 200/1e6*0.10 = 0.02127; haiku: 500/1e6*0.10 + 100/1e6*0.50 = 0.0001
assert_eq "session 1: total cost rounds to \$0.02" "0.02" "$(printf '%s' "$marker" | jq '([.models[].cost_usd] | add * 100 | round) / 100')"

# Test 4: second session on the same PR accumulates (PATCH), not a fresh comment
run_hook "$work/transcript.jsonl"
body2=$(cat "$work/state/comment_body.txt")
marker2=$(printf '%s\n' "$body2" | sed -n '/<!--claude-code-usage/,/-->/p' | sed '1d;$d')
assert_eq "session 2: sessions count accumulates to 2" "2" "$(printf '%s' "$marker2" | jq -r .sessions)"
assert_eq "session 2: input tokens double" "7000" "$(printf '%s' "$marker2" | jq '[.models[].input_tokens] | add')"
assert_eq "session 2: only one comment id ever used (PATCH, not new comment)" "https://github.com/testowner/testrepo/pull/42#issuecomment-1001" "$(cat "$work/state/comment_url.txt")"

[[ -f "$work/state/unhandled.log" ]] && { echo "FAIL: unhandled gh calls:"; cat "$work/state/unhandled.log"; fail=1; }

if [[ "$fail" -eq 0 ]]; then
  echo "All pr-cost-comment.sh tests passed."
else
  echo "pr-cost-comment.sh tests FAILED."
fi
exit "$fail"
