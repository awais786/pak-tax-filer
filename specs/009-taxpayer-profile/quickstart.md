# Quickstart: Taxpayer Profile (009)

Validates the feature end to end. Contracts: [contracts/profile-api.md](contracts/profile-api.md).

## Prerequisites

002 built; stack running (`docker compose up -d`); migrations applied
(`docker compose exec backend alembic upgrade head`); a fresh demo user:

```bash
docker compose exec backend python -m app.cli create-user --email profile-demo@example.com
```

## Scenarios

1. **Setup is required (US1):** log in at `http://localhost:5173` as the new user. Expected: you
   land on `/profile`. Typing `http://localhost:5173/` brings you back to `/profile`.
2. **Setup page content:** tax year shows only 2025-26; ATL yes/no has nothing selected; the FBR
   link opens FBR's "Check Active Taxpayer Status" page in a new tab; the residency notice is
   shown. Saving without an ATL answer is refused.
3. **Save:** choose "No", save. Expected: the home page opens; reopening `/profile` shows "No".
   From login to the home page takes under 1 minute (SC-001). Logging out from the setup step
   works and the step reappears at the next login.
4. **Change (US2):** switch to "Yes", save, reopen. Expected: "Yes"; nothing else changed.
5. **Backend enforcement:** run the tests:

   ```bash
   docker compose exec backend pytest tests/profile
   docker compose exec frontend npm test -- ProfilePage
   ```

   Expected: all pass, including unsupported tax year → `422`, unknown field → `422`, no profile
   → `require_profile` `409`, and one row per user after two saves.
6. **Follow-ups (US3, after 003–006 are built):** upload a synthetic certificate, open the tax
   page (no ATL question), the wealth page, and call `calculate_income_tax` with a personal
   access token without `atl`. Expected: each uses the profile's tax year and ATL status.
