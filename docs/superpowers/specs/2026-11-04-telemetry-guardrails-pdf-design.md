# 008 Telemetry, Guardrails and PDF Export: Design

**Date:** 2026-11-04 · **Status:** Proposed · **Feature:** 008 (README milestone 8) ·
**Governed by:** [Constitution](../../../.specify/memory/constitution.md)

## Intent

README milestone 8: "Telemetry, guardrail tests, CI (lint/type-check/tests + an eval-accuracy
gate), PDF export with the validation-status banner." CI moved to 001 at the lead's request, and
the eval gates come with 003 (extraction, on `main`) and 006 (retrieval, on every PR), so 008
covers the three remaining parts: seeing how the app and its AI calls behave, proving the
constitution's guardrails hold across the whole app, and exporting results as PDFs that can't be
mistaken for advice.

**Goals:** telemetry for requests and every AI call with no user content; one guardrail suite
for Principles I, III and IV plus structural import rules; PDF export of the tax result and the
wealth statement with a banner on every page. The MVP is complete when this is done (roadmap).

**Non-goals:** page-usage analytics, alerting, hosted dashboards; new CI jobs beyond the
guardrail job (001/003/006 own the rest); filing-ready forms or the IRIS layout; emailing or
storing PDFs.

**Anti-goals:** telemetry that records prompts, replies, figures or emails (Principle V); a PDF
page without the banner (Principle IV); a guardrail that only some features test.

## Parts and decisions (Saifullah)

| Part | Chosen | Rejected |
|---|---|---|
| Telemetry | **A. OpenTelemetry** (industry standard; GenAI conventions for AI calls), printed to logs until the lead approves a local **Jaeger** viewer in Docker Compose (stack addition, asked in the PR) | B. own `ai_calls` table + page (home-made, redo later); C. hosted LLM observability (third party, new vendor and key) |
| Guardrail tests | **B. cross-app behaviour suite + `import-linter` rules** (engine, rates and reconciliation may not import `anthropic`) | A. behaviour suite only (catches only what tests exercise) |
| PDF banner | **B. label + validation status**: "Not yet reviewed by a tax practitioner. Not tax advice. Demo data only." plus "All figures are from confirmed certificates", the rule-check warnings (or "No warnings"), and for the workflow "Approved by you on [date]" | A. label only (ignores "validation-status"); C. full audit appendix (beyond MVP) |
| PDF generation | **A. HTML templates → WeasyPrint** on the server, banner as a repeated page header | B. ReportLab (layout by hand in code); C. headless Chromium (~300 MB, heavier) |

## Telemetry

- **Recorded:** each backend request (endpoint, duration, status) via the standard FastAPI
  instrumentation; database call timing via the SQLAlchemy instrumentation; each AI call
  (feature: extraction / tax summary / assistant / workflow agent; model; duration; input and
  output tokens; outcome: passed, check failed and replaced, timed out, fallback).
- **Never recorded:** prompts, replies, document contents, figures, emails, tokens or cookies;
  also no user or session ids, route templates only (no raw paths with ids), and no SQL text.
  *(Builder's call: the conservative reading of Principle V.)*
- **Where:** logs by default; Jaeger once approved (a setting switches the exporter).

## Guardrail suite

`backend/tests/guardrails/`, its own CI job, one file per principle:
- **I:** a fake AI returning made-up numbers never changes a tax, wealth or workflow result;
  import rules keep `anthropic` out of the engine, rates and reconciliation.
- **III:** unconfirmed certificates never reach the tax page, wealth page, MCP tools or workflow;
  the workflow cannot calculate without approval for the current inputs.
- **IV:** assistant answers are always cited and out-of-corpus questions refused; every result
  screen and every PDF page carries the label.

It reuses the per-feature guardrail tests' fixtures (005, 006, 007) rather than duplicating them.
The job is backend-only: it checks the API's `label` field and the PDFs; the screens' label tests
stay in the frontend job (004 T013, 005 T011) and are listed in the suite's README.
*(Builder's call.)*

## PDF export

- Tax result (004: figures, breakdown with rule locations, separate balances) and wealth
  statement (005: rows, reconciliation, result in words); a download button on each page; the
  workflow's result screen reuses the tax PDF with its approval date.
- Generated on each click from the same recalculated result; never stored.
- **No AI-written text in PDFs** (004's and 005's summaries, 007's research note): only
  code-computed figures, code-written messages and retrieved passages with citations, so a PDF is
  deterministic and needs no AI call. *(Builder's call: Principles I and VII.)*
- **Banner text:** the existing label from 004/005/006 ("Not yet reviewed by a tax practitioner.
  Not tax advice.", unchanged, so the guardrail checks one string) plus "Demo data only." and the
  validation status:
  - tax PDF: "All figures are from your confirmed certificates" and 003's rule-check warnings on
    those certificates (the same checks 007's validation step uses), or "No warnings";
  - wealth PDF: "Salary figures are from your confirmed certificates; other rows were entered by
    you" and 005's provisional notes, or "No warnings";
  - workflow tax PDF: also "Approved by you on [date]".
  *(Builder's call; consistent with 003–007.)*
- Blocked or not-ready results export nothing; the button is disabled with the reason.

## Stack

Only **Jaeger** (a new service in Docker Compose) is a stack component needing the lead's
approval. WeasyPrint, the OpenTelemetry SDK and `import-linter` are libraries inside the existing
backend, as 002 treated `pwdlib` and `react-router`; WeasyPrint's system packages (Pango) are
noted in the PR. *(Builder's call; follows 002's precedent.)*

## Done when

- Every AI call and request appears in telemetry with no user content (tested).
- The guardrail job fails if any Principle I, III or IV rule is broken, including an import
  rule.
- Every page of every exported PDF carries the label and validation status (tested by reading
  the PDF back).

## Left to the plan

Exporter settings, span and attribute names, import-linter configuration, template layout,
Docker packages for WeasyPrint, and the export endpoints.

## Addendum 2026-11-12: after the stack change, 006 and 007

The parts and decisions above stand, with these changes (decided by Saifullah unless marked):

- **Telemetry goes to the logs only; no viewer in 008** (Saifullah, option A of three: logs only;
  logs plus an opt-in local Jaeger; a hosted service). Telemetry is for developers, never users,
  so the "Activity" page 006's navigation reserved is dropped. Spans are printed to the backend
  logs with OpenTelemetry's console exporter; no new stack component, no approval needed, nothing
  on the server. A viewer (e.g. Jaeger) can be added later with an exporter setting and no code
  changes; the PR says so in one line. Checked while deciding: Jaeger idles at about 13 MB
  (154 MB image), so it was the new component, not its weight, that ruled it out.
- **Gemini, not Claude.** AI-call spans use OpenTelemetry's current GenAI names
  (`gen_ai.provider.name="gcp.gemini"` for the AI Studio endpoint; `gen_ai.operation.name`
  `generate_content`, `embeddings` or `execute_tool`; `gen_ai.request.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`), not the older
  `gen_ai.system="anthropic"`. These conventions are still "Development" and recently moved to
  their own repository, so the names live in one place in our code. *(Claude's call.)*
- **Eight AI uses, five call sites:** extraction, the tax and wealth summaries, Ask's answers,
  embeddings (search, corpus build, MCP search), and 007's document, validation and research
  agents. One wrapper around the five places that call Gemini covers all of them. Outcomes add
  "question limit reached" (006, 007) to passed, check failed, timed out and fallback.
- **Import rules** keep `google.genai`, `app.rag`, `app.documents.extraction` and the workflow's
  agents out of the tax engine, the rates and the reconciliation.
- **Guardrail suite** also gathers what 006 and 007 now prove: answers always cited and number-
  checked (including scales such as "10m"), the agents' read-only tools, and the approval gate
  (including the race 007's review fixed).
- **PDF library stays WeasyPrint**, measured on our backend image: +70 MB disk and 71 MB peak
  memory for a two-page render, against fpdf2's 58 MB and 59 MB, whose built-in fonts also can't
  draw characters such as "–". Fine for the 1 GB server.
- **PDF buttons:** the Tax page and Guided filing's result share 007's `TaxResultView`, so one
  Download PDF button there covers both, plus the wealth page. The guided-filing PDF keeps 007's
  cited passages but not its research note (AI-written text stays out of PDFs, as above).
