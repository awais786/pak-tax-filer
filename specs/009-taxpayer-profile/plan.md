# Implementation Plan: Taxpayer Profile

**Branch**: `009-taxpayer-profile` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-taxpayer-profile/spec.md`

## Summary

One `taxpayer_profiles` row per user (tax year, ATL status), read and saved through
`GET`/`PUT /api/profile`, with a `get_profile` helper and a `require_profile` dependency for
other features. The React app gets a profile page (setup and edit) and a `RequireProfile` guard
inside 002's `RequireAuth` that sends users without a profile to `/profile`. A final phase,
done after 003–006 are built, switches them to read the profile. Decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript on Node 24 (frontend), as in 001

**Primary Dependencies**: none added; FastAPI, SQLAlchemy 2.0 async, Alembic, React,
`react-router` (from 002)

**Storage**: PostgreSQL 17: new table `taxpayer_profiles` ([data-model.md](data-model.md))

**Testing**: pytest against the test database (002's `conftest.py`); Vitest + React Testing
Library

**Target Platform**: local Docker Compose (from 001)

**Project Type**: web application (backend + frontend)

**Performance Goals**: complete setup and reach the app in under 1 minute (SC-001)

**Constraints**: no identity or residency fields (FR-004); only supported tax years accepted
(FR-003); one profile per user enforced by the database (FR-001)

**Scale/Scope**: demo scale; 2 endpoints, 1 page, 1 route guard, plus follow-up changes to
003–006

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | The profile only supplies ATL status to 004's engine; no calculation here |
| II. Authoritative sources | PASS | The ATL link goes to FBR's own page (R4); supported years follow 004's FBR-sourced rates |
| III. Human confirmation | N/A | No extraction |
| IV. Honest output | PASS | Residency notice states who the app covers (FR-005) |
| V. Synthetic data only | PASS | No name, CNIC, NTN or residency stored (FR-004) |
| VI. Test-first | PASS | Every story's tests are written before its code (tasks.md) |
| VII. MVP scope | PASS | README "one taxpayer profile, one configurable tax year"; nothing beyond it |
| Stack | PASS | No new dependencies |
| Secrets | PASS | None |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-taxpayer-profile/
├── plan.md
├── research.md          # R1–R6
├── data-model.md        # taxpayer_profiles
├── quickstart.md
├── contracts/
│   └── profile-api.md   # GET/PUT /api/profile, helpers, frontend routes, follow-ups
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── settings.py               # + SUPPORTED_TAX_YEARS
│   └── profile/
│       ├── models.py             # TaxpayerProfile
│       ├── service.py            # get_profile, save_profile (upsert)
│       ├── dependencies.py       # require_profile
│       └── router.py             # /api/profile
├── alembic/versions/0009_taxpayer_profiles.py
└── tests/profile/
    ├── test_profile_api.py
    └── test_require_profile.py

frontend/src/
├── profile/ProfileContext.tsx    # profile from GET /api/profile
├── profile/RequireProfile.tsx
└── pages/ProfilePage.tsx (+ .test.tsx)
```

**Structure Decision**: a `backend/app/profile/` package beside 002's `auth/`, so 003–007
import `get_profile`/`require_profile` from one place. The migration is numbered `0009` to match
the feature; Alembic orders by `down_revision`, which is set at implementation to the latest
migration then present.

## Complexity Tracking

No constitution violations; nothing to justify.
