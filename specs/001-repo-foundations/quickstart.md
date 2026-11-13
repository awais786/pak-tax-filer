# Quickstart: validating Repo Foundations (001)

**Prerequisites:** Docker + Docker Compose, `uv`, Node 26+ (research R1), bash and `jq` (Git Bash on
Windows; `winget install jqlang.jq`). Python is provided by `uv`.

## 1. Start the app (User Story 1, SC-001)

```bash
git clone <repo> && cd pak-tax-filer
docker compose up -d
docker compose exec backend alembic upgrade head
```

| Check | Expected |
|---|---|
| `curl http://localhost:8000/health` | `{"status":"ok"}` ([contract](contracts/health.md)) |
| Open `http://localhost:5173` | Placeholder page |
| `docker compose exec db psql -U postgres -c "\dx"` | `vector` listed |
| `docker compose exec backend pytest` | All tests pass |
| `docker compose exec frontend npm test` | All tests pass |

## 2. Tax-rates guard (User Story 2, SC-002)

In Claude Code, in this repo:

1. Ask Claude to create `backend/app/tax/rates/example.py`. **Expected:** an approval prompt
   with the FBR reason. Reject → file not created. Repeat and approve → file created.
2. Ask Claude to run `ls backend/app/tax/rates`. **Expected:** the same approval prompt.
3. Ask Claude to edit any file outside that folder. **Expected:** no tax-rates prompt.

## 3. Shared rules (User Story 3, SC-003, SC-004)

1. Ask Claude to write a badly indented `.py` file. **Expected:** saved formatted (our
   `format-on-write.sh`), and any pylint findings reported (the lead's `check-python.sh`).
   Ask for a force-push. **Expected:** the lead's `git-safety.sh` asks first.
2. Ask Claude to run `pytest`. **Expected:** runs without asking.
3. Ask Claude to `git push`. **Expected:** asks first.
4. Ask Claude to read `.env`. **Expected:** refused.

## 4. Cross-platform (SC-006)

Repeat sections 2 and 3 on a second OS (Windows and macOS/Linux). **Expected:** same results.

## 5. Conventions and CI (User Story 4, SC-007, SC-008)

0. `uv run --no-project --with pytest pytest .claude/hooks/tests`. **Expected:** all five hooks
   (ours and the lead's) pass their sample-input tests.

1. Open a pull request that breaks a backend test. **Expected:** the `backend` CI job fails and
   the PR is marked failing. Fix it → green.
2. Open a pull request with a badly formatted `.tsx` file. **Expected:** the `frontend` job fails
   on the Prettier check.
3. In Claude Code, open a file in `backend/`. **Expected:** `backend/CLAUDE.md` and the
   `python-backend`, `api`, `testing-quality` and `security` rules apply (`/memory` lists
   them); the root `CLAUDE.md` still contains the lead's engineering rules.
4. Ask Claude to "build a backend feature" and to "review this change". **Expected:** it uses the
   `fastapi-feature` and `code-review` skills; `/agents` lists `backend-reviewer` and
   `frontend-reviewer`.
5. Open `docs/api-conventions.md`. **Expected:** paths, bodies, errors, auth and keeping-in-step
   rules as in [contracts/api-conventions.md](contracts/api-conventions.md).

## 6. Continuous deployment (User Story 5, SC-009; added 2026-11-10)

1. Merge a small change into `main`. CI runs; when it passes, the "Deploy" workflow starts,
   builds both images, deploys them and checks the site. The live site serves the change within
   10 minutes, and nobody signed in to the VM.
2. In Actions → Deploy → Run workflow, enter an earlier commit: the site serves that one.
3. A CI run for a pull request (or a failing one) starts no deploy.
4. With the deploy key, `ssh <user>@<vm> whoami` doesn't run `whoami`: it is refused as an
   invalid deploy request.

## 7. Responsive redesign (User Story 6, SC-010, SC-011; added 2026-11-10)

1. Start the app and log in as the demo user. In the browser's device toolbar, open every page
   at 320, 768, 1024 and 1440 px wide, in light and dark mode. **Expected:** no sideways scroll;
   the nav is in the header from 720 px and at the bottom below; the current page is marked.
2. With no confirmed salary certificate for the profile's year, open Home. **Expected:**
   Documents is next; Tax and Wealth say they need a confirmed salary certificate. Confirm one:
   Tax becomes next.
3. Tab through Home, Documents and Wealth with the keyboard only. **Expected:** a visible focus
   ring everywhere, "Skip to content" first, every action reachable.
4. Run Lighthouse (mobile) on the production build for login, home and wealth. **Expected:**
   performance at least 90, accessibility at least 95.

## 8. Contract checks (User Story 7, SC-012 to SC-014)

1. `uv run --project backend python scripts/validate_contracts.py --all`. **Expected:** exit 0
   in under 30 seconds; a feature with no ticked task is skipped as not started (SC-013,
   SC-014). (Run 2026-11-13 with features 001–008 all started: exit 0 in 3 seconds.)
2. In a throwaway branch, plant each violation in turn and rerun: remove `GET /health` from the
   app; add an undocumented `GET /api/debug`; add a fourth tool name to a copy of 006's
   `mcp-tools.md` with 006 marked started. **Expected:** exit 1 each time, naming the feature,
   file and item.
3. On branch `001-…`, untick nothing and break `/health`; let Claude finish a turn.
   **Expected:** the failures are shown, Claude isn't blocked. Tick every non-manual task and
   repeat. **Expected:** Claude is blocked with the failure message until `/health` is fixed.
4. Open a pull request with the `/health` break. **Expected:** the `contracts` CI job fails.
5. Open `docs/contracts.md`. **Expected:** how to define a contract, run the check and read its
   failures.
