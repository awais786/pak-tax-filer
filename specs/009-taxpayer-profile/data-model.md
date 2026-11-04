# Data Model: Taxpayer Profile (009)

## taxpayer_profiles

| Column | Type | Rules |
|---|---|---|
| `id` | UUID, primary key | as 002's tables |
| `user_id` | UUID, not null, **unique**, references `users.id` on delete cascade | one profile per user (FR-001) |
| `tax_year` | text, not null | one of `SUPPORTED_TAX_YEARS` (today only `2025-26`), checked on save (FR-003) |
| `on_atl` | boolean, not null | ATL status; no "unknown" value (FR-002) |
| `created_at` | timestamp with time zone, not null, default now | |
| `updated_at` | timestamp with time zone, not null, default now, set on every save | |

No other columns: no name, CNIC, NTN or residency (FR-004, Principle V).

**Relationships:** `users` 1 — 0..1 `taxpayer_profiles`.

**States:** no profile → profile saved. A saved profile is only ever replaced by a new save,
never deleted on its own (it goes when the user is deleted).

**Migration:** `backend/alembic/versions/0009_taxpayer_profiles.py`, creating the table and its
unique key; its downgrade drops the table.
