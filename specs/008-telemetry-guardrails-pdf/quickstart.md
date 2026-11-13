# Quickstart: Telemetry, Guardrails and PDF Export (008)

Validates the feature end to end. Contract:
[contracts/pdf-and-telemetry.md](contracts/pdf-and-telemetry.md).

## Prerequisites

Features 001–007 built; stack running; a demo user with a profile, a confirmed synthetic salary
certificate, a bank certificate and a saved wealth statement.

## Scenarios

1. **PDFs (US1):** on the Tax page click Download PDF. Expected: within 5 seconds a PDF matching
   the screen; every page shows the label, "Demo data only." and "All figures are from your
   confirmed certificates" with "No warnings". Repeat on the Wealth page (salary-from-certificates
   line) and on a done workflow run (approval date). For a blocked tax result the button is
   disabled with the reason.
2. **Guardrails (US2):**

   ```bash
   docker compose exec backend lint-imports
   docker compose exec backend pytest tests/guardrails
   ```

   Expected: both pass. Then, in a throwaway branch, plant one break per principle and check each
   fails, reverting after each: add `import google.genai` to `app/tax/engine.py` (`lint-imports`
   fails, I); let `confirmed_documents` return `needs_review` documents too (both its status filter and
   its every-field-confirmed check, which is a second layer: removing one alone is caught by the other)
   (`test_principle_3.py` fails, III); remove the banner from `base.html`
   (`test_principle_4.py` fails, IV).
3. **Telemetry (US3):** with `OTEL_EXPORTER=console`, run upload, tax, ask and a workflow run.
   Expected: the backend logs show a span per request (route templates only) and per AI call with
   model, tokens and outcome. Search the logs for the demo email and a document id: no matches.
   (No viewer in 008: telemetry is read in the logs, amended 2026-11-12.)
4. **Tests:**

   ```bash
   docker compose exec backend pytest tests/telemetry tests/reports
   docker compose exec frontend npm test -- DownloadPdfButton
   ```

   Expected: all pass.
