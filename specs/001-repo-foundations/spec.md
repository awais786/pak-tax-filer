# Feature Specification: Repo Foundations

**Feature Branch**: `001-repo-foundations`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Repo foundations (README milestone 1). Give the project a running, empty application skeleton and a Claude Code setup that enforces the constitution from day one: one command starts the database (with vector search enabled), backend and frontend on the README's ports; a CLAUDE.md guide for Claude Code with the key rules and commands; a shared guard that pauses and asks a human to approve any AI change to the tax-rates module, explaining rates must come from FBR's gazetted documents (asks, does not block); automatic formatting of every file the AI writes; shared permission settings (allowed without asking: tests, linters, formatters, read-only git; must ask: push, deletions; never: reading .env secrets); README setup section updated for the FastAPI backend. Out of scope: auth, database tables, tax logic, CI, real data." Source design: `docs/superpowers/specs/2026-11-03-repo-foundations-design.md`.

## Clarifications

### Session 2026-11-03

- Q: When Claude tries to change a tax-rates file through a shell command instead of its file-edit tool, should the guard also pause for approval? → A: Yes. Any shell command that mentions the tax-rates folder also asks for approval (best effort); PR review remains the final backstop.

- Q: The lead's issues #4 and #5 ask for CI, folder guides, topic rules, reusable guides, reviewers and API conventions from the start; where do they go? → A: Into feature 001 as User Story 4 (FR-015 to FR-020), since they are project setup. CI moves here from feature 008. OpenSpec in those issues is replaced by Spec Kit (lead agreed).

### Session 2026-11-04

- Q: Now that the hooks are bash scripts (like the lead's #10), what automated checks run on them? → A: Tests only: CI runs each hook (ours and the lead's) against sample inputs and checks the response; no lint or type checks for bash.
- Q: The lead's issue #16 asks for automated contract validation (machine-checkable contracts, hooks, reusable scripts, Spec Kit integration, CI); where does it go? → A: Into feature 001 as User Story 5 (FR-021 to FR-027), like issues #4/#5 became User Story 4. Contracts become a small machine-checkable file per feature checked against the app's generated API schema (design addendum, approach A).
- Q: When should the check block the AI assistant from finishing? → A: Only when the current feature's last non-manual task is ticked (a completion claim); mid-feature it shows failures without blocking. Features not started are skipped, and tasks marked `(manual)` are never counted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start the whole app with one command (Priority: P1)

A developer clones the repository, follows the README's setup section, and with a single
command gets all three parts of the application running locally: the database, the backend
and the frontend. Each part shows it is alive, and each part's test suite can be run.

**Why this priority**: every later feature (002–008) is built on this skeleton. Without it,
nothing else can be developed or demonstrated.

**Independent Test**: on a machine with the README's prerequisites, clone the repo, run the
documented start command, and check that the backend reports healthy, the frontend shows a
placeholder page, vector search is available in the database, and both test commands pass.

**Acceptance Scenarios**:

1. **Given** a fresh clone and the README's prerequisites, **When** the developer runs the
   documented start command, **Then** the database, backend and frontend all start without
   further setup.
2. **Given** the app is running, **When** the developer opens the backend's health address,
   **Then** it reports that the backend is healthy.
3. **Given** the app is running, **When** the developer opens the frontend address, **Then**
   a placeholder page is shown.
4. **Given** the app is running, **When** the developer checks the database, **Then** vector
   search support is enabled.
5. **Given** the app is running, **When** the developer runs the README's backend and
   frontend test commands, **Then** each runs at least one test and all pass.

---

### User Story 2 - AI changes to tax rates need human approval (Priority: P2)

When the AI coding assistant tries to change anything in the tax-rates module, it pauses and
asks the developer to approve the change, explaining that tax rates must come only from FBR's
gazetted documents. The developer can approve or reject. Nothing is silently changed.

**Why this priority**: tax rates are the most sensitive data in the project (constitution
Principle II). The guard must exist before feature 004 adds the rates, so they are never
unprotected.

**Independent Test**: ask the AI assistant to edit a file in the tax-rates module and confirm
that an approval prompt appears with the FBR reason; approve once and reject once, and check
the file changed only when approved.

**Acceptance Scenarios**:

1. **Given** the shared AI settings are in place, **When** the AI assistant attempts to create,
   edit or overwrite a file in the tax-rates module, **Then** the developer is asked to approve
   it, and the prompt states that rates must come from FBR's gazetted documents.
2. **Given** the approval prompt is shown, **When** the developer rejects it, **Then** the file
   is left unchanged.
3. **Given** the approval prompt is shown, **When** the developer approves it, **Then** the
   change is applied.
4. **Given** the shared AI settings are in place, **When** the AI assistant runs a shell command
   that mentions the tax-rates module's folder, **Then** the same approval prompt appears.
5. **Given** the AI assistant edits a file outside the tax-rates module, **When** the edit runs,
   **Then** no tax-rates approval prompt appears.

---

### User Story 3 - The AI assistant follows the project's shared rules (Priority: P3)

Anyone working on the repository with the AI coding assistant gets the same rules
automatically: a guide file that tells the assistant the project's rules and commands, files
the assistant writes are formatted automatically, and a shared set of permissions decides what
the assistant may do freely, what it must ask about, and what it must never do.

**Why this priority**: it keeps every contributor's AI-assisted work consistent with the
constitution, but the app can be developed without it, unlike Stories 1 and 2.

**Independent Test**: in a fresh clone, have the AI assistant (a) write a badly formatted file,
(b) run the test suite, (c) attempt a push, and (d) attempt to read a secrets file; check that
(a) comes out formatted, (b) runs without a prompt, (c) asks first, and (d) is refused.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** the AI assistant starts a session, **Then** it has access
   to a guide describing the constitution's key rules, the repo layout, and the commands to
   run, test and format the project (added to the lead's existing root guide, which keeps its
   engineering rules).
2. **Given** the AI assistant writes or edits a source file, **When** the write completes,
   **Then** the file is automatically formatted to the project's standard.
3. **Given** the shared permissions, **When** the AI assistant runs tests, linters, formatters
   or read-only version-control commands, **Then** it does so without asking.
4. **Given** the shared permissions, **When** the AI assistant tries to push to a remote or
   delete files, **Then** it asks the developer first.
5. **Given** the shared permissions, **When** the AI assistant tries to read a local secrets
   file, **Then** it is refused.

---

### User Story 4 - Shared engineering conventions and automated checks (Priority: P4)

Added at the lead's request (issues #4 and #5). Every change is checked automatically before it
can be merged, and the AI assistant follows the same written conventions for each part of the
codebase: topic-specific rules, guides for the backend and frontend, reusable how-to guides for
building a backend or frontend feature and for code review, and specialised reviewers for
backend and frontend changes. Backend and frontend agree on one documented API convention.

**Why this priority**: it raises quality for every later feature, but Stories 1–3 are needed
first for there to be anything to check.

**Independent Test**: open a pull request with a failing test and one with a formatting error;
both are marked as failing and cannot be merged until fixed. In a Claude Code session, ask for a
backend feature and a code review; the matching guide and reviewer are used.

**Acceptance Scenarios**:

1. **Given** a pull request, **When** it is opened or updated, **Then** lint, format, type and
   test checks run automatically for the backend and the frontend, hook tests run for the
   hooks, and the result is shown on the pull request.
2. **Given** any of those checks fails, **When** someone tries to merge, **Then** the pull
   request is marked as failing.
3. **Given** a Claude Code session, **When** the assistant works in the backend or frontend
   folder, **Then** it has that folder's guide and the rules for the topic it is working on
   (architecture, backend, frontend, API, testing, security).
4. **Given** a developer asks the assistant to build a backend feature, a frontend feature, or
   review code, **When** it starts, **Then** it follows the matching reusable guide.
5. **Given** a change to backend or frontend code, **When** a review is requested, **Then** a
   reviewer specialised for that part can be used.
6. **Given** a new API endpoint, **When** it is designed, **Then** a written API convention
   defines its path, request and response shapes, errors and authentication.

---

### User Story 5 - Contracts are checked automatically (Priority: P5)

Added at the lead's request (issue #16). Each feature's API, database tables and task list are
checked automatically against what its spec promises: while the AI assistant implements a
feature, when it tries to call the feature finished, and on every pull request. Problems come
with a message naming the feature and what is wrong, and a feature can't be called complete or
merged while a mandatory check fails.

**Why this priority**: it protects every later feature from drifting away from its spec, but
needs the app (Story 1), the hooks setup (Story 3) and CI (Story 4) to exist first.

**Independent Test**: plant one violation of each kind in a throwaway change (an endpoint
missing from the app, a missing field, a missing database column, a fourth MCP tool, an unticked
task when the feature is claimed done) and check that the script, the assistant hook and the
pull request each report it by name and fail; remove it and check all pass.

**Acceptance Scenarios**:

1. **Given** a started feature whose app is missing an endpoint, method, success status or
   required field from its contract, **When** the check runs, **Then** it fails naming the
   feature, the contract file and the item.
2. **Given** an endpoint in the app that no feature's contract lists, **When** the check runs,
   **Then** it fails naming the endpoint (the framework's own documentation pages excepted).
3. **Given** a started feature whose data model lists a table or column the app lacks, **When**
   the check runs, **Then** it fails naming the table or column.
4. **Given** features that have not started, **When** the check runs, **Then** they are skipped
   and do not fail it.
5. **Given** the assistant is mid-feature, **When** it finishes a turn with failing checks,
   **Then** the failures are shown and work is not stopped.
6. **Given** the current feature's last non-manual task is ticked, **When** the assistant tries
   to finish with any check failing, **Then** it is refused with the failure messages.
7. **Given** a pull request, **When** it is opened or updated, **Then** the same check runs and a
   failure marks the pull request failing.
8. **Given** a feature is ready for its pull request, **When** the developer reviews it, **Then**
   Spec Kit's own comparison of code with spec, plan and tasks is used, separately from the
   pass/fail check.

### Edge Cases

- A required port (backend or frontend) is already in use on the developer's machine: the
  start fails with a message that names the busy port.
- The developer has no local secrets file: the skeleton still starts, since no feature in 001
  needs secrets.
- The AI assistant changes a tax-rates file through a shell command that never names the
  tax-rates folder (e.g. a script that builds the path itself): the guard cannot detect this;
  human review of the PR remains the backstop.
- The formatter cannot parse a file the AI assistant wrote (e.g. a syntax error): the file is
  kept as written and the assistant is told formatting failed, rather than the write being
  lost.
- A contributor works on Windows, macOS or Linux: the guard and formatting behave the same on
  all three.
- A started feature has an API but no machine-checkable contract file: the check fails, naming
  the missing file.
- A task can only be done by a person (a manual check, a second operating system): it is marked
  `(manual)` and never blocks the assistant.
- The developer stops a session while the completion check is failing: they can; the pull
  request check still blocks the merge.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST start its database, backend and frontend with a single command
  documented in the README.
- **FR-002**: The backend MUST be reachable on port 8000 and the frontend on port 5173, as the
  README states.
- **FR-003**: The backend MUST expose a health check that reports when it is running.
- **FR-004**: The frontend MUST serve a placeholder page.
- **FR-005**: The database MUST have vector search support enabled.
- **FR-006**: The backend and frontend MUST each have a test command, run as documented in the
  README, with at least one passing test.
- **FR-007**: The repository MUST contain a guide file for the AI coding assistant covering the
  constitution's key rules, the repo layout, and the commands to run, test and format.
- **FR-008**: The repository MUST reserve a fixed location for the tax-rates module, even
  though the rates themselves arrive in feature 004.
- **FR-009**: Any attempt by the AI assistant to create, edit or overwrite a file in the
  tax-rates module MUST pause for the developer's approval, with a message stating that rates
  must come from FBR's gazetted documents. Any shell command the AI assistant runs that
  mentions the tax-rates folder MUST trigger the same prompt (best effort). It MUST ask, not
  block.
- **FR-010**: Every source file the AI assistant writes or edits (the file types listed in the
  hooks contract) MUST be formatted automatically to the project's standard.
- **FR-011**: Shared AI permissions MUST allow tests, linters, formatters and read-only
  version-control commands without asking; require approval for pushing and deleting; and
  forbid reading local secrets files.
- **FR-012**: The guard, formatting and permissions MUST be shared through the repository, so
  every contributor gets them on clone, and MUST work on Windows, macOS and Linux. They MUST be
  added alongside the lead's existing shared hooks and settings (#10), never replacing them.
- **FR-013**: The README's setup section MUST be updated so its commands work for the chosen
  backend (replacing the Django-specific step).
- **FR-014**: The skeleton MUST NOT include authentication, database tables, tax logic or any
  real data.
- **FR-015**: Automated checks MUST run on every pull request: lint, format and type checks and
  tests for the backend and the frontend, and tests for the hooks (each hook run against sample
  inputs); a failure MUST mark the pull request as failing. Each check MUST use the same tool the repository's hooks already use for it (one
  linter per language), so local and automated checks agree.
- **FR-016**: The backend and frontend folders MUST each have their own guide for the AI
  assistant, kept short and not repeating the root guide.
- **FR-017**: The repository MUST provide topic rules for the AI assistant covering
  architecture, backend, frontend, API design, testing and security. Topics the lead's rules
  (#10) already cover MUST be extended in those files, not duplicated; the backend rule MUST
  describe the FastAPI backend, not Django.
- **FR-018**: The repository MUST provide reusable guides for building a backend feature,
  building a frontend feature, and reviewing code, and the root guide MUST say when to use each.
- **FR-019**: The repository MUST provide a backend reviewer and a frontend reviewer for the AI
  assistant, each focused on that part's conventions, security and test coverage.
- **FR-020**: The repository MUST contain one written API convention covering paths, request
  and response shapes, errors, authentication and how changes are kept in step between backend
  and frontend.
- **FR-021**: Each feature with an API MUST have a machine-checkable contract file, beside its
  written contract, listing every endpoint's path, method, success status and required request
  and response fields.
- **FR-022**: One reusable check MUST compare the app with every started feature's contract
  file, the tables and columns in its data model, the assistant tools named in feature 006, and
  its task list; every problem MUST be reported with the feature, file and item, and any
  problem MUST give a failing result.
- **FR-023**: Features with no ticked task MUST be skipped; tasks marked `(manual)` MUST NOT be
  counted; endpoints present in the app but in no contract MUST fail the check, except the
  framework's own documentation pages.
- **FR-024**: When the AI assistant finishes a turn, the check MUST run for the current feature:
  mid-feature it MUST show failures without stopping work; once the feature's last non-manual
  task is ticked, it MUST refuse to let the assistant finish until every check passes. No check
  MUST run after every individual edit.
- **FR-025**: CI MUST run the same check on every pull request and push to `main`; a failure MUST
  mark the pull request failing.
- **FR-026**: The comparison of code with spec, plan and tasks MUST use Spec Kit's own steps
  (converge, analyze) before a feature's pull request, kept separate from the pass/fail check.
- **FR-027**: Documentation MUST explain how to define a contract, run the check locally and read
  its failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with the README's prerequisites goes from fresh clone to all three
  parts running in under 10 minutes, using only the README's setup section.
- **SC-002**: 100% of attempted AI changes to the tax-rates module through file edits, and of
  AI shell commands that mention the tax-rates folder, produce an approval prompt with the FBR
  reason.
- **SC-003**: 100% of attempts by the AI assistant to read a local secrets file are refused.
- **SC-004**: Every source file written by the AI assistant during a session ends up formatted,
  with no manual formatting step.
- **SC-005**: The backend and frontend test commands each pass on a fresh clone.
- **SC-006**: The same setup works unchanged on Windows and on macOS or Linux.
- **SC-007**: 100% of pull requests show automated check results, and a pull request with a
  failing test or formatting error is marked as failing.
- **SC-008**: Each of the six rule topics (in the lead's rule files or ours), both folder guides,
  the three reusable guides and both reviewers exists and is referenced from the root guide.
- **SC-009**: 100% of planted contract violations (missing endpoint, wrong method, missing field,
  undocumented endpoint, missing column, extra assistant tool, unticked task at completion) are
  reported by name with a failing result, by the script, the assistant hook and CI.
- **SC-010**: The check for all features finishes in under 30 seconds (no server started, no full
  test suite run).
- **SC-011**: With only feature 001 started, the check passes (no false failures from planned
  features).

## Assumptions

- This feature is developer tooling rather than end-user functionality, so its "users" are the
  repo's developers (Saifullah, the lead) and the AI coding assistant itself. The README names
  some of the artefacts directly (Docker Compose, `CLAUDE.md`, Claude Code hooks), so those
  names appear here as requirements, not as implementation choices.
- The backend framework is FastAPI, as fixed by the constitution; other technical choices are
  made in the plan.
- The tax-rates guard covers the AI assistant's file edits and any shell command that names the
  tax-rates folder. Shell commands that reach the folder without naming it are not reliably
  detectable; PR review by the lead is the backstop.
- Actions not listed in the shared permissions (e.g. installing packages) fall back to the AI
  assistant's default behaviour of asking first.
- Developers have the prerequisites in the updated README installed: Docker + Docker Compose,
  `uv` (which provides Python), Node 24+ (the README's Node 20 has reached end of life), and
  bash with `jq` for the shared hooks (Git Bash on Windows).
- The lead's #10 already provides a root `CLAUDE.md`, rules for security, Python, git workflow
  and testing quality, and hooks for risky git operations and lint after edits. This feature
  builds on those files and fills only the gaps (design addendum, 2026-11-04).
- No secrets are needed for this feature; the local secrets file is first needed in feature 003.
