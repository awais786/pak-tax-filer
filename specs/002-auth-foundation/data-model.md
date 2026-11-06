# Data Model: Authentication Foundation and Taxpayer Profile (002)

Created by Alembic migration `0002_auth_tables`. All timestamps are UTC.

## users

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `email` | text | required; stored trimmed and lower-cased; **unique** (FR-001) |
| `password_hash` | text | required; Argon2 hash, never the password (FR-003) |
| `created_at` | timestamptz | required, defaults to now |

No identity fields (Principle V).

## sessions

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | required; references `users.id`, deleted with the user |
| `token_hash` | text | required; SHA-256 of the cookie token; **unique** |
| `created_at` | timestamptz | required, defaults to now |
| `expires_at` | timestamptz | required; `created_at` + 7 days (FR-009) |

**Lifecycle:** created at login → valid while `now < expires_at` → deleted at logout (FR-008)
or when used after expiry. A user may have several sessions (several devices).

## login_failures

| Column | Type | Rules |
|---|---|---|
| `id` | bigint | primary key |
| `email` | text | required; trimmed and lower-cased; indexed |
| `attempted_at` | timestamptz | required, defaults to now; indexed with `email` |

Used only for throttling (FR-007): an email is throttled while it has 10 or more rows with
`attempted_at` in the last 15 minutes. Rows older than 15 minutes have no effect.

**Known limitation:** rows are never deleted, so the table grows over time. This is harmless at
demo scale; a cleanup job can be added when the app has real traffic.

## taxpayer_profiles (added 2026-11-04)

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | required; references `users.id`, deleted with the user; **unique** (FR-016) |
| `tax_year` | text | required; one of `SUPPORTED_TAX_YEARS` (today only `2025-26`), checked on save (FR-017) |
| `on_atl` | boolean | required; no "unknown" value (FR-016) |
| `created_at` | timestamptz | required, defaults to now |
| `updated_at` | timestamptz | required, defaults to now; set on every save |

No other columns: no name, CNIC, NTN or residency (FR-018, Principle V). Created by
`0003_taxpayer_profiles` (amended 2026-11-05: planned inside `0002_auth_tables`, but 0002 had
already been applied, and applied migrations are never edited).

**Lifecycle:** no profile → saved → replaced by each later save; deleted only with the user.
