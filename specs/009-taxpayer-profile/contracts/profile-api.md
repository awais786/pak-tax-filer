# Contract: Profile API, helpers and frontend routes

Base path `/api/profile`. JSON bodies; errors are `{"detail": "<message>"}` (002's convention).
Both endpoints are protected by 002's `current_user` (`401` `{"detail": "Not logged in."}`
without a session) and only ever touch the caller's own profile (FR-014).

## GET /api/profile

`200` always (for a logged-in user):

```json
{ "profile": { "tax_year": "2025-26", "on_atl": true, "updated_at": "2026-11-04T10:00:00Z" },
  "supported_tax_years": ["2025-26"] }
```

`"profile": null` when the user has none yet.

## PUT /api/profile

Request (`Content-Type: application/json`):

```json
{ "tax_year": "2025-26", "on_atl": false }
```

| Outcome | Status | Body |
|---|---|---|
| Created or replaced | `200` | the `profile` object as in `GET` |
| `tax_year` not in `supported_tax_years` | `422` | `{"detail": "Tax year 2024-25 is not supported."}` |
| `on_atl` missing or not a boolean, unknown fields | `422` | FastAPI validation error |

Unknown fields (e.g. `cnic`) are rejected, not ignored (FR-004). Saving changes nothing else the
user has saved (FR-008).

## Helpers for other features (`app/profile/`)

- `get_profile(db, user) -> TaxpayerProfile | None`
- `require_profile` (dependency) → the profile, or `409` `{"detail": "Set up your profile first."}`

## Frontend routes

| Path | Who can see it | Behaviour |
|---|---|---|
| `/profile` | logged-in users | Setup (no profile) or edit form: tax year select (from `supported_tax_years`), ATL yes/no radio with no default, link "Check your ATL status on FBR's website" (R4, new tab), notice "This app covers people who live in Pakistan and earn a salary."; 002's logout button. Saving without an ATL answer shows "Tell us whether you are on the ATL." Save → `PUT`; then `next` or `/`. |

Every other page wrapped in `RequireAuth` is also wrapped in `RequireProfile`: with
`"profile": null` it redirects to `/profile?next=<path>`. Covers FR-005 to FR-007.

## Follow-up changes (after 003–006 are built)

| Feature | Change |
|---|---|
| 003 | Upload endpoint depends on `require_profile`; the upload's `tax_year` is the profile's; the tax-year consistency rule compares with it; `TAX_YEAR` setting removed (FR-010) |
| 004 | `GET /api/tax/{tax_year}` drops the `atl` query parameter and reads `on_atl` via `get_profile`; no profile → `blocked_reason: "needs_atl_answer"` with message "Set your ATL status in your profile." and the page links to `/profile`; the tax page's ATL question removed (FR-011) |
| 005 | Wealth page opens on the profile's tax year (FR-013) |
| 006 | `calculate_income_tax` takes no `tax_year` or `atl` input and uses the token owner's profile (no profile → the same `needs_atl_answer` body); `validate_salary_information` keeps its `tax_year` input and checks it against the profile's (FR-012) |
