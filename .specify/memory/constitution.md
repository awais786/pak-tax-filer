# Pak Tax Filer Constitution

## Core Principles

### I. Deterministic Tax Math (NON-NEGOTIABLE)

- Every tax liability, slab lookup, withholding credit, and wealth-statement reconciliation
  MUST be computed by plain, deterministic code. The same inputs MUST always give the same
  output.
- An LLM MUST NOT produce, adjust, round, or "sanity-check" any of these numbers. The AI model
  is allowed in exactly three places: extracting fields from documents, the RAG assistant, and
  explaining a number that has already been computed.
- Monetary values MUST use exact decimal arithmetic (e.g. Python `Decimal`), never binary
  floating point. Rounding rules MUST be explicit and match FBR's.
- An LLM-generated explanation MUST quote the computed numbers it was given and MUST NOT
  introduce new figures.

**Rationale:** a tax figure a user files has to be reproducible and auditable. An LLM can be
confidently wrong about arithmetic, and the user cannot tell when that happens.

### II. Authoritative Sources Only (NON-NEGOTIABLE)

- Tax rates, slabs, thresholds, and §151 withholding rates MUST come from FBR's own published
  or gazetted documents: the Income Tax Ordinance 2001 as amended by the relevant Finance Act,
  and FBR's own guides.
- Third-party calculators, blogs, and news articles MUST NOT be used as a source for any rate,
  not even to "double-check" one.
- Rates MUST live in one dedicated, versioned tax-rates module, keyed by tax year. Each value
  MUST record its source document, section, tax year, and the date it took effect.
- Changes to the tax-rates module MUST be called out explicitly in review, and the project's
  Claude Code hooks MUST guard the module against unreviewed edits.

**Rationale:** during planning, third-party Pakistani tax calculators were found to disagree
with each other. FBR's own documents are the only source that can be defended.

### III. Human Confirmation Before Use (NON-NEGOTIABLE)

- A value extracted by AI MUST be shown to the user with its confidence. The user MUST
  explicitly confirm or correct it before any calculation, report, or agent uses it.
- Unconfirmed extracted data MUST NOT flow downstream. The system MUST enforce this, not just
  the UI.
- The agentic workflow MUST stop at a human-approval gate before calculation. No agent may
  skip or auto-approve this gate.

**Rationale:** extraction from scanned or varied certificates is probabilistic. The user, not
the model, is the authority on what their documents say.

### IV. Honest, Labelled Output (NON-NEGOTIABLE)

- Every exported report (PDF or otherwise) MUST carry an unmissable "not yet
  practitioner-reviewed" label until a tax practitioner has reviewed the app.
- The app MUST NOT present anything as authoritative tax advice.
- Every answer from the RAG assistant MUST cite the corpus passages it relied on. When a
  question falls outside the corpus, it MUST say so explicitly instead of guessing.

**Rationale:** users may act on this output in a legal filing. Overstating certainty is the
most harmful failure this product can have.

### V. Synthetic Data Only (NON-NEGOTIABLE)

- Until a tax practitioner and a legal review have signed off, the app, its tests, evals,
  fixtures, and demos MUST use synthetic or demo data only.
- Real taxpayer documents, CNICs, NTNs, bank details, or salary records MUST NOT be committed,
  uploaded, logged, or sent to any external API.

**Rationale:** handling real financial PII carries legal and privacy obligations that this
project has not taken on yet.

### VI. Test-First Calculation, Measured AI

- The tax engine and reconciliation logic MUST be built test-first. Test cases MUST be worked
  examples derived from FBR sources, each citing its source. A failing test MUST exist before
  the code that makes it pass.
- AI features MUST be measured, not assumed. Extraction MUST have a labelled eval dataset with
  per-field accuracy. RAG MUST have a retrieval eval. CI MUST fail when accuracy drops below
  the agreed threshold.
- Guardrails (Principles I, III, IV) MUST have automated tests that prove each one holds.

**Rationale:** deterministic code can be proven correct with tests; AI components can only be
held to a measured bar. Both need to be checked automatically, every time.

### VII. MVP Scope Discipline

- The MVP covers one resident individual taxpayer, salaried or not, for tax years TY2026 and
  TY2027 (amended 2026-11-13, feature 010). Incomes: salary and bonuses, property (rent),
  business (including freelance and consultancy), profit on debt, dividends, capital gains and
  other sources, each under its legal treatment (normal, separately taxed, final, exempt,
  adjustable withholding). The engine applies the 75% salary test and its regime; Zakat,
  charitable donations and pension contributions; and tax withheld and advance tax, giving one
  amount payable or refundable.
- Incomes are typed by the user or come from confirmed documents. The two document types stay:
  a salary certificate and a bank profit certificate.
- Anything the engine doesn't cover (other deductions and credits, losses, depreciation, perk
  valuation, minimum and turnover tax) MUST be shown as unsupported, never guessed.
- The MCP server exposes exactly three tools: `search_tax_documents`,
  `calculate_income_tax`, `validate_salary_information`.
- Out-of-scope items (companies and associations of persons, non-residents, agricultural
  income, tax years before TY2026, IRIS login or auto-filing, real user documents) MUST NOT be
  built without an approved spec that amends the scope first.
- Simplicity wins: the simplest design that meets an approved spec is preferred. Added
  complexity MUST be justified in the plan's Complexity Tracking.

**Rationale:** this is a learning project with a small team. A narrow scope done correctly is
worth more than a wide scope done approximately.

## Technology & Security Constraints

- **Stack:** FastAPI (backend), React + TypeScript (frontend), PostgreSQL + pgvector (data and
  embeddings), Google Gemini API, free tier (extraction, RAG, explanation; replaced the Claude
  API on 2026-11-08 with the lead's approval, recorded in 003's plan), Python MCP SDK (MCP server), Docker
  Compose (local environment). Adding,
  replacing, or removing a stack component requires the project lead's approval, recorded with
  its reason in the feature's `plan.md`; it does not require a constitution amendment.
- **Secrets:** API keys (e.g. `ANTHROPIC_API_KEY`) and credentials MUST live in local,
  uncommitted `.env` files and MUST NOT appear in code, logs, prompts, or commits.
- **Corpus:** the RAG corpus is a fixed, named set of sources: ITO §12, §13, §149, §7B, §151;
  the Wealth Statement (Form 116) guide; the salaried return (Form 114(1)) guide. Adding a
  source requires an approved spec.

## Development Workflow & Quality Gates

- **Per feature:** `superpowers:brainstorming` design doc (saved to
  `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) → `/speckit-specify` →
  `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → GitHub
  Issues → `/speckit-implement`.
- **Specs are the source of truth.** When code and spec disagree, either the spec is amended
  first or the code is fixed. Specs live in `specs/NNN-feature-name/`.
- **Traceability:** every GitHub Issue MUST link to the spec and task it implements.
- **Review before build:** a feature's spec and plan MUST be reviewed by the project lead
  before its implementation starts.
- **Merge gates:** until CI exists (feature 001), the project lead's PR review is the merge
  gate. Once CI exists, it MUST pass lint, type checks and tests before merge; the
  eval-accuracy gate joins CI when the first eval exists (features 003 and 006). Every plan
  MUST pass the Constitution Check in `plan-template.md`.

## Governance

- This constitution overrides all other practices and guidance in the repository. Where the
  README or a spec conflicts with it, the constitution wins until it is amended.
- **Amendments** require a written proposal (what changes and why), approval from the project
  lead, a version bump, and an update to every affected spec or plan.
- **Versioning** follows semantic versioning. MAJOR: a principle is removed or redefined.
  MINOR: a principle or section is added or materially expanded. PATCH: wording or
  clarification only.
- **Compliance:** every plan, PR, and review MUST check against these principles. A violation
  MUST either be fixed or be recorded in Complexity Tracking with justification and lead
  approval. Runtime development guidance lives in `CLAUDE.md`.

**Version**: 1.3.0 | **Ratified**: 2026-11-02 | **Last Amended**: 2026-11-13
