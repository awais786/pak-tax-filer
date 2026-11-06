# Contract: Auth API

Base path `/api/auth`. Request and response bodies are JSON. Errors are
`{"detail": "<message>"}`. The session is carried only by the `session` cookie
(see [research.md](../research.md), R2).

## POST /api/auth/login

Request (`Content-Type: application/json` required):

```json
{ "email": "demo@example.com", "password": "at-least-8-chars" }
```

| Outcome | Status | Body | Cookie |
|---|---|---|---|
| Success | `200` | `{"email": "demo@example.com"}` | sets `session` |
| Unknown email or wrong password | `401` | `{"detail": "Invalid email or password."}` | none |
| 10+ failures for this email in 15 min | `429` | `{"detail": "Too many attempts. Try again later."}` | none |
| Missing or invalid fields (email 3–254 characters, password 1–1,024) | `422` | FastAPI validation error, without the rejected values | none |
| Not `Content-Type: application/json` | `415` | `{"detail": "Content-Type must be application/json."}` | none |

The email is trimmed and lower-cased before use. A failed attempt (401) is recorded for
throttling; a throttled attempt (429) does not check the password.

## POST /api/auth/logout

No body required (`Content-Type: application/json`; otherwise `415` and the session is kept). Otherwise always `204`. Deletes the current session if
there is one and clears the `session` cookie.

## GET /api/auth/me

Protected. With a valid session: `200` `{"email": "demo@example.com"}`. Otherwise: `401`
`{"detail": "Not logged in."}`.

## Protecting other endpoints

Any endpoint that depends on `current_user` returns `401` `{"detail": "Not logged in."}` when the
session is missing, unknown, logged out or expired, and otherwise receives the logged-in user.
Covers FR-010.

## Taxpayer profile: /api/profile (added 2026-11-04)

Both endpoints depend on `current_user` and only touch the caller's own profile (FR-023).

### GET /api/profile

`200` always: `{"profile": {"tax_year": "2025-26", "on_atl": true, "updated_at": "2026-11-04T10:00:00Z"}, "supported_tax_years": ["2025-26"]}`, with `"profile": null` when the user has none.

### PUT /api/profile

Request: `{"tax_year": "2025-26", "on_atl": false}` (`Content-Type: application/json`).

| Outcome | Status | Body |
|---|---|---|
| Created or replaced | `200` | the `profile` object as in `GET` |
| `tax_year` not supported | `422` | `{"detail": "Tax year 2024-25 is not supported."}` |
| `on_atl` missing or not a boolean; unknown fields (e.g. `cnic`) | `422` | FastAPI validation error, without the rejected values |
| Not `Content-Type: application/json` | `415` | `{"detail": "Content-Type must be application/json."}` |

### Helpers for other features (`app/profile/`)

- `get_profile(db, user)` → the profile or `None`.
- `require_profile` (dependency) → the profile, or `409` `{"detail": "Set up your profile first."}`.

Covers FR-016 to FR-018, FR-021 to FR-023.
