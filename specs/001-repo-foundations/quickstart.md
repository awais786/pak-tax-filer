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
