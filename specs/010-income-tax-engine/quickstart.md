# Quickstart: Simple Income Tax Calculator (feature 010)

Prove the feature works. Contract: [contracts/calculator-api.md](contracts/calculator-api.md);
rules: [research.md](research.md).

## Prerequisites

`docker compose up -d`, migrations at head (`docker compose exec backend alembic upgrade head`),
and a signed-in user with a TY2026 taxpayer profile (synthetic data only).

## Automated

| Check | Command | Expected |
|---|---|---|
| Worked examples (all signed) | `docker compose exec backend pytest tests/tax` | all pass, including 004's (unchanged) and 010's |
| Sign-off | (part of the above: `test_sign_off.py`) | fails if any example is unsigned |
| API | `docker compose exec backend pytest tests/tax/test_calculator_api.py` | 200 / 409 / 415 / 422 cases pass |
| Guardrails | `cd backend && uv run lint-imports && uv run pytest tests/guardrails` | the calculator imports no AI |
| Contract | `uv run --project backend python scripts/validate_contracts.py --feature 010` | exit 0 |
| Frontend | `docker compose exec frontend npm test` | `CalculatorPage.test.tsx` passes |

## By hand

1. Open http://localhost:5173/calculator. Enter salary 250,000 a month and rent 140,000 a month;
   calculate. Expect: taxable income Rs 4,344,000; salary share 69.06%; non-salaried table; total
   tax Rs 1,107,600; effective rate 23.7%; monthly salary tax Rs 25,000, take-home Rs 225,000; the
   practitioner label and the not-covered note.
2. Add a bonus: a "bonus adds Rs X" line appears; add dividends: a 15% line and a filer vs
   non-filer line (15% vs 30% deducted).
3. Clear every field and calculate: "enter at least one income", no figures.
4. Enter bank profit above Rs 5,000,000: refused with the reason, no figures.
5. Open the Tax page: unchanged.
