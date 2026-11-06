# Implementation Plan: Authentication Foundation and Taxpayer Profile

**Branch**: `002-auth-foundation` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-auth-foundation/spec.md`

## Summary

Custom, cookie-based authentication in the FastAPI backend: users, sessions and login-failure
tables; Argon2 password hashing; login, logout and "who am I" endpoints; a reusable
`current_user` dependency that protects endpoints; throttling after 10 failures in 15 minutes;
and a developer command to create demo users. The React app gets a login page, protected
routes, a logout button and a redirect to login on `401`. The taxpayer profile (User Stories 4
and 5, added 2026-11-04) is one `taxpayer_profiles` row per user (tax year, ATL status), read and
saved through `GET`/`PUT /api/profile`, with `get_profile`/`require_profile` for later features
and a `RequireProfile` guard inside `RequireAuth`. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript on Node 24 (frontend), as in 001

**Primary Dependencies**: added: `pwdlib[argon2]` (backend), `react-router` (frontend); existing:
FastAPI, SQLAlchemy 2.0 async, Alembic, React, Vite

**Storage**: PostgreSQL 17: new tables `users`, `sessions`, `login_failures`,
`taxpayer_profiles` ([data-model.md](data-model.md))

**Testing**: pytest against a separate test database; Vitest + React Testing Library

**Target Platform**: local Docker Compose (from 001)

**Project Type**: web application (backend + frontend)

**Performance Goals**: log in and reach a protected page in under 30 seconds (SC-001); complete
the profile setup in under 1 minute (SC-007)

**Constraints**: cookie `HttpOnly` + `SameSite=Lax`; no password or session token stored or
logged in readable form; same response for unknown email and wrong password

**Scale/Scope**: demo scale; 5 endpoints, 1 command, 3 pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | N/A | No calculations |
| II. Authoritative sources | PASS | No rates; the ATL link goes to FBR's own page (R12) |
| III. Human confirmation | N/A | No extraction |
| IV. Honest output | PASS | "Demo data only" notice on the login page (FR-014) |
| V. Synthetic data only | PASS | Demo users only; no identity fields on users or the profile (no name, CNIC, NTN, residency); passwords and tokens stored only as hashes |
| VI. Test-first | PASS | Every story's tests are written before its code (tasks.md) |
| VII. MVP scope | PASS | README milestone 2 "Taxpayer profile + auth"; one profile, one tax year; sign-up, reset and verification excluded (FR-015) |
| Stack | PASS | `pwdlib` and `react-router` are libraries within the existing backend and frontend, not new stack components; Cognito excluded |
| Secrets | PASS | No new secrets; the cookie `Secure` flag is a setting, not a secret |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-foundation/
├── plan.md
├── research.md          # R1–R14
├── data-model.md        # users, sessions, login_failures, taxpayer_profiles
├── quickstart.md
├── contracts/
│   ├── auth-api.md      # login, logout, me, current_user, profile API
│   └── cli-and-ui.md    # create-user command, frontend routes (incl. /profile)
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── db.py                     # async engine + session dependency
│   ├── settings.py               # DATABASE_URL, cookie Secure flag, SUPPORTED_TAX_YEARS
│   ├── cli.py                    # create-user command
│   └── auth/
│       ├── models.py             # User, Session, LoginFailure
│       ├── passwords.py          # hash / verify (pwdlib Argon2)
│       ├── sessions.py           # create, look up, delete sessions
│       ├── throttle.py           # count and record failures
│       ├── dependencies.py       # current_user
│       └── router.py             # /api/auth/login, logout, me
│   └── profile/
│       ├── models.py             # TaxpayerProfile
│       ├── service.py            # get_profile, save_profile (upsert)
│       ├── dependencies.py       # require_profile
│       └── router.py             # /api/profile
├── alembic/versions/0002_auth_tables.py
└── tests/
    ├── conftest.py               # test database + rolled-back transactions
    └── auth/
        ├── test_passwords.py
        ├── test_login_logout.py
        ├── test_throttle.py
        ├── test_protected.py
        └── test_cli.py
    └── profile/
        ├── test_profile_service.py
        ├── test_profile_api.py
        └── test_require_profile.py

frontend/
├── vite.config.ts                # proxy /api → backend:8000
└── src/
    ├── api/client.ts             # fetch helper; 401 → /login
    ├── auth/AuthContext.tsx      # current user from /api/auth/me
    ├── auth/RequireAuth.tsx
    ├── pages/LoginPage.tsx (+ .test.tsx)
    ├── pages/HomePage.tsx (+ .test.tsx)
    ├── pages/ProfilePage.tsx (+ .test.tsx)
    ├── profile/ProfileContext.tsx
    ├── profile/RequireProfile.tsx
    └── components/LogoutButton.tsx
```

**Structure Decision**: auth code lives in its own `backend/app/auth/` package so later
increments (sign-up, reset) and other features import `current_user` from one place; the profile
lives beside it in `backend/app/profile/` so 003–007 import `get_profile`/`require_profile` from
one place. The profile table has its own migration, `0003_taxpayer_profiles` (amended
2026-11-05: 0002 had already been applied when the profile was built).

## Complexity Tracking

No constitution violations; nothing to justify.
