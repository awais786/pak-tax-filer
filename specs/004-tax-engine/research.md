# Research: Deterministic Tax Engine (004)

Each decision: what was chosen, why, and what else was considered. Legal sources are in the
[design doc](../../docs/superpowers/specs/2026-11-03-tax-engine-design.md).

## R1. Pure calculation core

- **Decision:** `backend/app/tax/engine.py` exposes `calculate(inputs: TaxInputs, rates:
  TaxYearRates) -> TaxResult`: no database, network, clock or AI. Steps run in a fixed order
  (eligibility → salary tax → surcharge → profit tax → credits → balances → rounding) and each
  appends a breakdown step.
- **Rationale:** the same inputs always give the same output (Principle I); trivially testable;
  reusable by the MCP tool `calculate_income_tax` (feature 006).
- **Alternatives:** calculation inside the API route (harder to test and reuse).

## R2. Rates format

- **Decision:** one Python module per tax year in the guarded folder `backend/app/tax/rates/`,
  e.g. `ty2026.py`, holding frozen dataclasses. Every number is a `Decimal` built from a string,
  and every rule carries `source_document`, `location` and `finance_act`. A registry maps
  `"2025-26"` to its module.
- **Rationale:** typed and checked by mypy; no parsing step that could turn `0.11` into a float;
  one file to review per tax year; the 001 guard hook already covers the folder.
- **Alternatives:** YAML or JSON (readable, but needs a loader and careful `Decimal` parsing, and
  typos surface only at runtime); database table (rates would change without code review).

## R3. Arithmetic and rounding

- **Decision:** all amounts are `Decimal`; intermediate results are never rounded; final amounts
  (salary tax, surcharge, profit tax, each balance) are rounded with
  `quantize(Decimal("1"), rounding=ROUND_HALF_UP)`, which matches §219 (under 50 paisa dropped,
  50 paisa or more up). Band tests use "does not exceed" for upper limits and "exceeds" for the
  surcharge and Rs 5 million limits, exactly as worded.
- **Alternatives:** banker's rounding (Python's default `ROUND_HALF_EVEN`: wrong for §219);
  rounding each step (could drift by a rupee from the law's single rounding).

## R4. Eligibility and provisional rules

- **Decision:** checked first; any failure returns a `TaxResult` with `blocked_reason` and no
  figures:
  - no taxpayer profile; no confirmed salary certificate;
  - summed bank profit > Rs 5,000,000;
  - salary share > 75% with and without bank profit in taxable income gives different answers;
  - taxable income > Rs 10,000,000 with and without bank profit gives different answers.
  *(Amended 2026-11-17: these last two are removed; s.8(1)(a) keeps bank profit out of taxable
  income, so taxable income is salary alone. See FR-012.)*
  Each provisional rule is a named constant in one place so it can be changed when the lead
  answers.

## R5. Inputs

- **Decision:** `backend/app/tax/service.py` builds `TaxInputs` from 003's
  `confirmed_documents(user_id, tax_year)`: sums taxable salary and tax deducted across salary
  certificates, and gross profit and tax withheld across bank certificates. ATL comes from the
  user's taxpayer profile (feature 002's `get_profile`; amended 2026-11-04). Results are
  recalculated on every request, never stored.

## R6. API

- **Decision:** `GET /api/tax/{tax_year}` (protected by `current_user`; ATL from the profile).
  Returns the result, breakdown, optional summary and the
  "not practitioner-reviewed" label text. `GET` because nothing changes on the server.

## R7. Breakdown text

- **Decision:** each step is generated from a fixed template with the actual numbers, plus the
  rule's `location` (e.g. "First Schedule, Part I, Division I, clause (2), row 3"). Amounts are
  formatted as `Rs 1,800,000`; rates as `11%`.

## R8. AI summary and the number check

- **Decision:** after a successful calculation, call Gemini (free tier; same pattern as 003: official `google-genai` SDK,
  `SUMMARY_MODEL` setting defaulting to `gemini-3.5-flash-lite`, effort `minimal` (amended 2026-11-10: `low` thinking used the token budget, cutting answers short, and often missed the 4 s limit; a reply that did not finish normally is now dropped), short output; first `claude-opus-5-5`) with the
  breakdown as data and an instruction to summarise in 2–3 plain sentences using only numbers
  from it. Then a plain-code check:
  - collect the **allowed set**: every number appearing in the rendered breakdown (amounts,
    rates, band limits, tax year);
  - extract every number from the summary (digits with optional commas and decimals, with or
    without `Rs`, `%`);
  - **reject** the summary if any extracted number isn't in the allowed set, or if it contains
    number words (`lakh`, `crore`, `million`, `thousand`, written-out numbers), since those can't
    be checked reliably.
  The call has a **4-second limit** so results stay within SC-004; a late, rejected or refused summary, or an API error, means no summary. The breakdown is always returned; the response waits for the summary at most 4 seconds.
  - **Added after review (2026-11-09):** the summary is also dropped if it says "refund" (the app never promises one, FR-013), uses payable words ("owe", "payable", "outstanding") when nothing is payable, or over-deduction words when nothing is over-deducted.
  - **Known limit:** a number from the breakdown can still be attached to the wrong figure ("your tax is Rs 600,000"). The breakdown beside it is the authoritative answer; this is accepted for the MVP.
- **Rationale:** enforces Principle I's "no new figures" mechanically instead of trusting the
  model.
- **Alternatives:** trusting the prompt (unenforced); asking a second model to verify (still
  non-deterministic).

## R9. Worked examples and sign-off

- **Decision:** `backend/tests/tax/worked_examples.yaml` lists every example: inputs, the
  hand-working step by step with the source row used, expected figures, and `signed_off_by` /
  `signed_off_date`. Tests are generated from this file, and a separate test **fails if any
  example lacks a sign-off**, which enforces FR-015 before the engine can pass CI. Examples
  cover each band (inside and at both limits), Rs 10,000,000 exactly and just above, Rs 5,000,000
  exactly and just above, a 50-paisa rounding case, several certificates, zero bank profit, a
  non-ATL user and each blocked case. Needs `pyyaml` (dev only).
- **Rationale:** the examples are reviewed as documents by a human, then executed as tests.

## R10. Band-continuity self-check

- **Decision:** a test loops over every tax year in the registry and asserts that each band's
  fixed amount equals the previous band's fixed amount plus its rate times its width. It would
  have caught FBR Circular 01's 345,000 / 615,000.
