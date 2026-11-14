# Guardrail suite (feature 008, User Story 2)

These tests prove the constitution's guardrails across the whole app, not one feature at a time.
CI's `guardrails` job runs `uv run lint-imports` and then `uv run pytest tests/guardrails` on
every pull request and every push to `main`; if a guardrail breaks, CI fails.

| File | Principle | What it proves |
|---|---|---|
| [`../../.importlinter`](../../.importlinter) | I | The tax engine, the rates and the wealth reconciliation never import Gemini (`google`), extraction, the RAG code or the guided run's agents, directly or through another module. |
| [`test_principle_1.py`](test_principle_1.py) | I: deterministic tax math | Every AI client answers with made-up numbers; the tax, wealth and guided results still equal the signed-off worked examples, and the made-up numbers are never shown. |
| [`test_principle_3.py`](test_principle_3.py) | III: human confirmation | With one confirmed and one unconfirmed salary certificate, the tax page, the wealth statement, the MCP tool and the guided gate count only the confirmed one; the guided result and its PDF need an approval. |
| [`test_principle_4.py`](test_principle_4.py) | IV: honest, labelled output | The assistant's answers are cited and number-checked (a "10m" no passage has is refused); out-of-corpus and Urdu questions are refused; the guided run's law comes only from search; every result and every page of every PDF carries the label. |

## Related tests elsewhere

These guard the same principles inside one feature and stay where they are:

| Test | Feature | Guards |
|---|---|---|
| `tests/tax/test_engine_imports.py` | 004 | The engine imports no AI, network or database code (I). |
| `tests/tax/test_worked_examples.py`, `tests/wealth/test_wealth_worked_examples.py` | 004, 005 | The calculations equal the signed-off examples (I). |
| `tests/wealth/test_reconcile_imports.py` | 005 | The reconciliation stays pure: no database, network, clock or AI (I). |
| `tests/mcp/test_mcp_tools.py` | 006 | The MCP tools use the app's own engine and rules and ignore unconfirmed certificates (I, III). |
| `tests/rag/test_checks.py` | 006 | The assistant's citation and number checks, scales included (IV). |
| `tests/workflow/test_gate.py` | 007 | No result without an approval of the current inputs; no agent text approves anything (III). |
| `tests/reports/test_pdfs.py` | 008 | The banner on every PDF page, figures equal to the JSON, no AI text (IV). |
| `frontend/src/pages/TaxPage.test.tsx`, `WealthPage.test.tsx`, `WorkflowPage.test.tsx`, `AskPage.test.tsx` | 004–007 | The practitioner label on every result screen (IV); these run in the frontend CI job. |

## Adding a guardrail

Put a cross-feature check here, in the file for its principle, using the existing fakes
(`no_real_ai` in `tests/conftest.py` fakes every AI client for every test). A test here should
fail if someone breaks the principle anywhere in the app; check that it does by breaking it once
on purpose (quickstart scenario 2).
