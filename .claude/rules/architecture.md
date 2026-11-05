# Architecture

Constitution Principles I and II in practice (`.specify/memory/constitution.md`).

- Tax liabilities, slabs, withholding credits and wealth reconciliation are computed by plain,
  deterministic Python with `Decimal` and explicit FBR rounding. No LLM call ever produces,
  adjusts, rounds or "checks" one of these numbers.
- Claude is used in exactly three places: extracting fields from documents, the RAG assistant,
  and explaining a number that has already been computed (quoting it, adding no new figures).
- Rates live only in `backend/app/tax/rates/`, keyed by tax year, each value with its FBR source
  document, section and tax year. The folder is guarded by a hook; call out every change in
  review.
- Keep logic in plain functions (`service.py`, the engine), not in routers or React
  components, so it can be tested without HTTP or a browser.
- AI-extracted values reach calculations only after the user confirms them, enforced by the
  backend, not just the UI (Principle III).
