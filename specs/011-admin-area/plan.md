# Implementation Plan: Admin Area

**Branch**: `011-admin-area` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-admin-area/spec.md`

## Summary

An internal admin area at `/admin` for the team running PakTaxFiler, built with starlette-admin
mounted in the FastAPI backend over the existing SQLAlchemy models (research R1, checked in a
throwaway run). Staff-only admin accounts are made from the command line and sign in with the app's
own hashed-token sessions under a separate 8-hour, `/admin`-scoped, `SameSite=Strict` cookie
(R2, R4). Admins see a dashboard, accounts (with an overview computed as the app computes it, read
without side effects), documents, the law library, saved telemetry and the audit log, all
read-only (R5, R6); they can disable or re-enable, delete (files first), sign out everywhere and
reset the reading limit, on taxpayer accounts only (R7). Every action and account view is
audit-logged (R8). Telemetry is queued by an exporter behind the existing content filter and
written in batches by a background task, kept 30 days (R9, R10). No AI anywhere (R14).

## Technical Context

**Language/Version**: Python ≥ 3.13 (backend). No frontend code changes except the dev proxy.

**Primary Dependencies**: FastAPI, async SQLAlchemy 2.1, Alembic, OpenTelemetry SDK (all existing);
**new: `starlette-admin` 1.0.x** (brings Jinja2, python-multipart, itsdangerous).

**Storage**: PostgreSQL: migration `0009_admin_area` (two `users` columns, `admin_audit_log`,
`telemetry_spans`) per [data-model.md](data-model.md).

**Testing**: pytest with the `client` fixture over the mounted admin (HTML pages and form posts),
service tests for the actions and the exporter/writer, the contract check (data-model tables),
import-linter, one Playwright e2e test (admin sign-in, disable an account).

**Target Platform**: the existing Docker Compose stack and the GCP e2-micro deployment (Caddy).

**Project Type**: web service (existing backend) with server-rendered admin pages.

**Performance Goals**: admin pages answer within normal page times on the 1 GB server; telemetry
saving adds no work to a request beyond appending to an in-memory queue (SC-006).

**Constraints**: one backend process in production (one telemetry writer); memory: bounded queue
(10,000 rows); no Redis; no outside requests from admin pages except the font noted in R12.

**Scale/Scope**: a handful of admins; telemetry volume of a small app (thousands of rows a day at
most), 30 days kept.

## Constitution Check

*GATE: checked before Phase 0 and again after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Deterministic tax math | The account page shows 004's result from its own engine; no AI anywhere in this feature (R14, guardrail test) | ✅ |
| II. Authoritative sources | No rate or rule added or changed | ✅ |
| III. Human confirmation | Admins can't change figures or confirm documents (FR-015); the account page reads confirmed documents only, through `confirmed_documents`; viewing never re-runs a guided run (R6) | ✅ |
| IV. Honest, labelled output | No new taxpayer-facing output | ✅ |
| V. Synthetic data only | No new kind of personal data; admin, tests and demos use synthetic accounts | ✅ |
| VI. Test-first, measured AI | Every rule test-first (tasks); guardrail tests extended (no secrets on admin pages, no AI in admin) | ✅ |
| VII. MVP scope | Admin area added by amendment 1.4.0 (2026-11-17) exactly as specified | ✅ |
| Technology & Security | New dependency `starlette-admin`: recorded here with its reason (R1), for the lead's approval in the PR. Secrets: `ADMIN_SECRET_KEY` only from the environment, never logged (R3) | ⚠️ lead approval in PR |
| Workflow: review before build | Building before the lead reviews spec and plan | ⚠️ see Complexity Tracking |

Re-check after Phase 1 design: unchanged (the data model and contract add nothing that touches
I–VI).

## Project Structure

### Documentation (this feature)

```text
specs/011-admin-area/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/admin-pages.md
├── checklists/requirements.md
└── tasks.md            (speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── admin/                 # new
│   │   ├── site.py            # build_admin(app): the starlette-admin instance, views, mount
│   │   ├── models.py          # AdminAuditEntry (the convention: each area's tables in models.py)
│   │   ├── auth.py            # AdminAuthProvider (R2)
│   │   ├── views.py           # ModelViews + row actions (R5–R7), dashboard and telemetry views
│   │   ├── actions.py         # the four actions as plain service functions (R7)
│   │   ├── audit.py           # record() (R8)
│   │   ├── overview.py        # account_overview(), dashboard counts (R6)
│   │   └── templates/         # local overrides (R12) and the account overview panel
│   ├── telemetry/
│   │   ├── models.py          # new: TelemetrySpan
│   │   ├── store.py           # new: DatabaseSpanExporter, writer, retention, summary (R9, R10)
│   │   └── setup.py           # listener skips spans while instrumentation is suppressed
│   ├── auth/
│   │   ├── models.py          # User.is_admin, User.disabled_at
│   │   ├── sessions.py        # create_session(..., lifetime=)
│   │   ├── router.py          # login refuses admin/disabled accounts
│   │   └── dependencies.py    # current_user refuses admin/disabled accounts
│   ├── tokens/service.py      # owner_of refuses admin/disabled accounts
│   ├── settings.py            # admin_secret_key, telemetry_store
│   ├── cli.py                 # create-admin
│   └── main.py                # lifespan (telemetry writer), build_admin(app)
├── alembic/versions/0009_admin_area.py
└── tests/
    ├── admin/                 # new: auth, pages, no-secrets, actions, audit, overview, telemetry page
    ├── auth/                  # admin/disabled refusals
    ├── telemetry/             # store: exporter filter, writer, retention, suppression
    └── guardrails/            # no AI in admin; no secrets on admin pages
deploy/Caddyfile               # /admin routed to the backend (R11)
frontend/vite.config.ts        # /admin proxied in development (R11)
e2e/tests/admin.spec.ts        # admin sign-in and disable
.importlinter                  # admin direct-import ban (R14)
```

**Structure Decision** (amended during T005: tables in each area's `models.py`, the contract check's convention; the site in `site.py` so models import without the library): one new backend package `app/admin/` (HTTP-facing views kept thin; logic in
`actions.py` and `overview.py` as plain functions, per the backend rules), one new telemetry module,
and small changes to auth, tokens, settings, CLI and `main.py`.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected because |
|---|---|---|
| Built before the lead reviewed spec and plan (constitution, Development Workflow: "Review before build") | Saifullah, 2026-11-17: "once you've reviewed go ahead and build it"; it ships in one PR with the 004 fix | Waiting would stall both; the lead still reviews spec, plan and code in the PR, and nothing merges without him (merge gate unchanged). Needs his approval in the PR. |
| New dependency `starlette-admin` (constitution, Technology & Security) | The lead asked for an admin library; his choice (fastapi-admin) needs Tortoise ORM and Redis and isn't maintained (R1) | Writing our own admin pages is several times the code; SQLAdmin's support couldn't be confirmed. Needs his approval in the PR. |
