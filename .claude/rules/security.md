# Security & Secrets

- Never commit or push API tokens, passwords, credentials, private keys, or
  any other secret — including in code, config, migrations, fixtures, test
  data, or commit messages.
- `ANTHROPIC_API_KEY` and any other credential lives in a local, uncommitted
  `.env` file (see README "Development setup"). Never hardcode it.
- Before committing, scan the diff for anything that looks like a key, token,
  or connection string with embedded credentials — not just files literally
  named `.env`.
- Synthetic/demo data only for now (see README "Non-negotiables") — no real
  user financial documents until a tax practitioner and legal review are in
  place.
- Tax and wealth-reconciliation arithmetic is deterministic code, never an
  LLM call — an LLM may only explain an already-computed result.
- Never log secrets, passwords, session tokens or personal data, and never put them in error
  messages or test output.
- Claude must not read `.env` files; the shared permissions deny it.
