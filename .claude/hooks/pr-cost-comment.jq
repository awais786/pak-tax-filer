# Reads a Claude Code transcript (slurped JSONL, -s) and returns per-model
# token totals + an estimated USD cost for this session.
#
# Pricing is $/MTok, current as of 2026-11-04 per
# https://platform.claude.com/docs/en/about-claude/pricing. Update here when
# Anthropic changes prices. An unrecognized model prices at $0 (under-reports
# cost rather than guessing); Claude Haiku 5.5's >100K-token-prompt tier and
# Claude Fable 5.1/Mythos pricing are not modeled.
def rate_for(model):
  if (model | test("opus-5-5")) then {input: 4, output: 20, cache_write: 5, cache_read: 0.20}
  elif (model | test("sonnet-5-5")) then {input: 2, output: 10, cache_write: 2.50, cache_read: 0.10}
  elif (model | test("haiku-5-5")) then {input: 0.10, output: 0.50, cache_write: 0.125, cache_read: 0.01}
  else {input: 0, output: 0, cache_write: 0, cache_read: 0}
  end;

[.[] | select(.message.usage != null and .message.model != null)
     | {model: .message.model, usage: .message.usage}]
| group_by(.model)
| map({
    model: .[0].model,
    input_tokens: (map(.usage.input_tokens // 0) | add),
    output_tokens: (map(.usage.output_tokens // 0) | add),
    cache_read_tokens: (map(.usage.cache_read_input_tokens // 0) | add),
    cache_creation_tokens: (map(.usage.cache_creation_input_tokens // 0) | add)
  })
| map(. + {
    cost_usd: (
      (.input_tokens / 1000000 * rate_for(.model).input) +
      (.output_tokens / 1000000 * rate_for(.model).output) +
      (.cache_creation_tokens / 1000000 * rate_for(.model).cache_write) +
      (.cache_read_tokens / 1000000 * rate_for(.model).cache_read)
    )
  })
