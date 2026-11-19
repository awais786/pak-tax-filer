# Quickstart: Admin Area (011)

Validates the feature end to end. Contract: [contracts/admin-pages.md](contracts/admin-pages.md);
tables: [data-model.md](data-model.md).

## Prerequisites

Stack running (`docker compose up -d`), migrations applied
(`docker compose exec backend alembic upgrade head`), at least one synthetic taxpayer with a
profile and a confirmed salary certificate (e.g. `demo@example.com`). Optional:
`ADMIN_SECRET_KEY` in the environment (research R3).

## Scenarios

1. **Create an admin (FR-001):**
   `docker compose exec backend python -m app.cli create-admin --email admin@example.com`; enter a
   synthetic password twice. Running it again with the same email, or with `demo@example.com`, is
   refused.
2. **Sign in (US1):** open `http://localhost:5173/admin`, sign in as the admin. Expected: the
   dashboard with counts. Signing in with `demo@example.com` or a wrong password shows
   "Invalid email or password."
3. **Staff-only (FR-002):** `POST /api/auth/login` as the admin → `401`.
4. **Look around (US1):** Accounts → open the demo account: tax year, ATL, documents, the Tax result
   as on the Tax page, the guided-run step. Audit log: one `view_account` entry. No page offers
   create, edit, delete, export or import; no page shows a hash.
5. **Act (US2):** on a throwaway synthetic taxpayer: Disable (their app sign-in is refused, their
   session ends), Re-enable, Sign out everywhere, Reset reading limit, then Delete account (its
   stored files are gone). The audit log lists each action once. None of the actions appears on an
   admin account.
6. **Telemetry (US3):** browse the app for a minute, open Telemetry: requests per day, error share,
   slowest routes, AI calls. Saved rows contain only the allowed attributes
   (`docker compose exec db psql -U postgres -d pak_tax_filer -c "select * from telemetry_spans limit 5"`).
7. **Tests:**

   ```bash
   docker compose exec backend pytest tests/admin tests/auth tests/telemetry tests/guardrails
   ```

   Expected: all pass. The e2e suite (`e2e/README.md`) includes an admin sign-in and disable test.
