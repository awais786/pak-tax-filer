# Feature Specification: Admin Area

**Feature Branch**: `011-admin-area`

**Created**: 2026-11-17

**Status**: Draft

**Input**: User description: the lead, 2026-11-16: "https://fastapi-admin-docs.long2ice.io/ — try
to integrate it also." Shaped with Saifullah on 2026-11-17 by brainstorming (he asked for what is
normal for this kind of application and chose at each step). Source design:
`docs/superpowers/specs/2026-11-17-admin-area-design.md` (the linked library is ruled out there:
it needs a different database library and Redis, and hasn't been released since 2022).
Constitution 1.3.0, to be amended (Principle VII) to include this feature.

## Clarifications

### Session 2026-11-17

Resolved from the design without a question (Saifullah asked for review then build):

- Q: Are admin sign-ins recorded in the audit log? → A: No; the audit log holds the four actions
  and account-detail views, as decided in the design. Failed admin sign-ins are counted by the
  sign-in throttle (FR-004).
- Q: What happens when two admins act on the same account at once? → A: Each completed action
  writes one audit entry; disabling or re-enabling twice is harmless; a delete of an account that
  no longer exists tells the admin so and writes no entry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the app at a glance (Priority: P1)

An admin, one of the people running PakTaxFiler, signs in to the admin area and sees how the app
is being used: headline counts on a dashboard, the list of taxpayer accounts, one account's
progress (profile, documents, tax result or refusal, guided-filing step), all documents, and the
law library. Nothing they look at can be changed from here, and opening one person's details is
recorded.

**Why this priority**: without it there is no way to see the app's state except by reading the
database; every other story builds on signing in and seeing accounts.

**Independent Test**: create an admin from the command line and two synthetic taxpayers with
different progress; sign in as the admin and check each page shows the right counts and details,
shows no secret, offers no way to create, edit or delete a record, and records one entry each time
an account's details are opened.

**Acceptance Scenarios**:

1. **Given** an admin account created from the command line, **When** the admin signs in at the
   admin area with its email and password, **Then** they see the dashboard.
2. **Given** a taxpayer account, a wrong password, or a disabled account, **When** someone tries to
   sign in to the admin area with it, **Then** they get the same generic refusal and no access.
3. **Given** taxpayers with profiles, documents in each status and guided runs at different
   steps, **When** the admin opens the dashboard, **Then** the counts match: taxpayer accounts,
   profiles set up, documents uploaded / confirmed / failed, guided runs per step, document
   readings in the last 24 hours against the per-user and app-wide limits, and Ask questions
   against the per-user and app-wide limits.
4. **Given** a taxpayer with a confirmed salary certificate and a profile, **When** the admin opens
   that account, **Then** they see its tax year and ATL status, its documents with their status,
   its tax result as the Tax page would show it (figures or the refusal reason), and its
   guided-filing step, and exactly one audit entry records that this admin viewed this account.
5. **Given** any admin page, **When** the admin looks for a way to create, edit or delete a
   record, **Then** there is none, and no page shows a password, a session or an access token, in
   any form.
6. **Given** a taxpayer whose guided run's inputs have changed since it last ran, **When** the
   admin opens that account, **Then** the run is shown as stored and nothing about the account
   changes.

---

### User Story 2 - Act on a taxpayer account (Priority: P2)

An admin handles the routine support cases: disabling an account that is being abused (and
re-enabling it), deleting an account when its owner asks, signing a user out of every device, and
resetting a user's daily limit on document readings. Every action is recorded, and the audit log
shows who did what to which account and when.

**Why this priority**: an admin area's job is to let the team act; these are the standard support
actions for an app holding personal data.

**Independent Test**: as an admin, take each action on a synthetic taxpayer and check its effect
in the app (sign-in refused or allowed, data and stored files gone, sessions ended, readings
possible again) and that the audit log has exactly one matching entry per action.

**Acceptance Scenarios**:

1. **Given** an active taxpayer, **When** the admin disables the account, **Then** the user is
   signed out everywhere, their access tokens stop working, and signing in to the app is refused
   with the same message as a wrong password; **When** the admin re-enables it, **Then** the user
   can sign in again.
2. **Given** a taxpayer with uploaded documents, **When** the admin deletes the account after a
   confirmation step, **Then** the account, its profile, documents, figures, statements and runs
   are gone and so are its stored files.
3. **Given** document storage that can't be reached, **When** the admin deletes an account,
   **Then** the deletion stops with a clear message, nothing is deleted from the account's records,
   and trying again later works.
4. **Given** a taxpayer signed in on two devices, **When** the admin signs them out everywhere,
   **Then** both sessions end and their access tokens keep working.
5. **Given** a taxpayer who has used all 10 document readings in the last 24 hours, **When** the
   admin resets their daily limit, **Then** the user can have a document read again.
6. **Given** an admin account, **When** another admin looks at it, **Then** none of the four
   actions is offered for it.
7. **Given** a series of actions and account views, **When** the admin opens the audit log,
   **Then** it lists each one, newest first, with the admin, the action, the account and the time,
   and offers no way to change or remove an entry.

---

### User Story 3 - See how the app is performing (Priority: P3)

An admin opens the telemetry page to see how the app has been behaving: how many requests it
handles each day, how many fail, which pages are slowest, and how the AI readings and the
assistant are doing (outcomes, how long they take, how much they use). It covers the last 30 days
and never contains anyone's content.

**Why this priority**: telemetry is already collected but lost; saving and showing it is valuable
but the app works without it.

**Independent Test**: make requests and AI calls (faked) with saving on, then check the telemetry
page's figures match them, that saved records hold only the permitted, content-free details, that
a failure to save never fails a request, and that records older than 30 days are removed.

**Acceptance Scenarios**:

1. **Given** requests and AI calls over several days, **When** the admin opens the telemetry
   page, **Then** it shows requests per day, the share that failed on the server's side, the
   slowest pages (typical and worst-case time), AI calls per feature by outcome, how long AI
   calls take, and tokens used per day.
2. **Given** any saved telemetry record, **When** it is inspected, **Then** it holds only the
   permitted details already allowed for the logs (page route, method, status, AI feature, model,
   outcome, token counts, timings) and nothing else.
3. **Given** saving telemetry fails, **When** a user makes a request, **Then** the request
   succeeds as normal.
4. **Given** records older than 30 days, **When** the clean-up runs, **Then** they are removed and
   newer ones kept.

---

### Edge Cases

- The last remaining admin: admins can't act on admin accounts, so no admin can be locked out by
  another; admin accounts are managed only from the command line.
- An account deleted after admins viewed or acted on it: its audit entries remain, shown by the
  account's identifier since its email is gone.
- Failed admin sign-ins are counted separately from the app's, so repeated failures on the public
  sign-in page can't lock an admin out of the admin area.
- An admin email already in use by a taxpayer: creating the admin is refused; a taxpayer account
  is never turned into an admin.
- An admin account tries to use the taxpayer app or the assistant's tools: refused as if signed
  out.
- Re-enabling an account doesn't bring back its old access tokens.
- Two admins acting on the same account at once: each completed action is recorded once;
  repeating disable or re-enable is harmless; deleting an account already deleted says so and
  records nothing.
- A taxpayer with no profile: their account page shows no tax year and the tax result's refusal
  reason ("set your ATL status").

## Requirements *(mandatory)*

### Functional Requirements

**Admin accounts and sign-in**

- **FR-001**: The system MUST let an operator create an admin account only from the command line,
  with an email and a password entered twice; it MUST refuse an email that already has an
  account, and MUST never turn an existing account into an admin.
- **FR-002**: Admin accounts MUST NOT be able to use the taxpayer app or the assistant's tools:
  signing in, using a session and using an access token MUST be refused for them as for a wrong
  password or no session.
- **FR-003**: The admin area MUST have its own sign-in, admitting only active admin accounts, with
  one generic refusal for every other case (taxpayer account, wrong password, disabled account,
  unknown email).
- **FR-004**: Admin sign-in failures MUST be throttled as the app's sign-in is (feature 002),
  counted separately from the app's failures.
- **FR-005**: An admin session MUST end after 8 hours, MUST be usable only in the admin area, and
  MUST NOT be sent by the browser from another site.

**Seeing (User Story 1)**

- **FR-006**: The admin area MUST show a dashboard with: taxpayer accounts; profiles set up;
  documents uploaded, confirmed and failed; guided runs per step; document readings in the last
  24 hours against the per-user (10) and app-wide (100) limits; Ask questions in the last 24 hours
  against the app-wide limit (200) and the most any user asked in the last hour against the
  per-user limit (30).
- **FR-007**: The admin area MUST list accounts with search by email, showing each account's
  email, when it was created, whether it is an admin and whether it is disabled.
- **FR-008**: An account's details MUST show its tax year and ATL status, its documents and their
  status, its tax result computed as the Tax page computes it (figures, or the refusal reason),
  and its guided-filing step as stored.
- **FR-009**: Viewing any admin page MUST NOT change any user's data (in particular a guided run
  is never re-run by being viewed).
- **FR-010**: The admin area MUST list documents (type, status, tax year, when uploaded, owner's
  email) and MUST NOT offer the uploaded files themselves.
- **FR-011**: The admin area MUST list the law library's documents with their passage counts.
- **FR-012**: Admin pages MUST NOT offer creating, editing or deleting records, other than the four
  actions of FR-014.
- **FR-013**: Admin pages MUST NOT show a password, a session or an access token, in any form
  (including stored hashes).

**Acting (User Story 2)**

- **FR-014**: An admin MUST be able to take these actions on a taxpayer account, and on no admin
  account:
  - (a) **disable**: the account is marked disabled, its sessions and access tokens are removed,
    and sign-in, sessions and tokens are refused for it everywhere with the generic refusal;
  - (b) **re-enable**: the account can sign in again (old tokens stay removed);
  - (c) **delete**: after a confirmation step, every stored file of the account's documents is
    removed first, then the account and all its records; if storage can't be reached, nothing is
    deleted and the admin is told, and retrying is safe;
  - (d) **sign out everywhere**: the account's sessions are removed (tokens kept);
  - (e) **reset the daily reading limit**: the account's document readings counted in the last
    24 hours are cleared so it can have documents read again.
- **FR-015**: Admin actions MUST NOT change a user's figures, confirm a document or edit a profile
  (constitution Principle III).

**Audit log**

- **FR-016**: The system MUST record one audit entry for each action of FR-014 and each opening of
  an account's details, holding the admin, the action, the account and the time, and no content
  (no emails, figures or document text).
- **FR-017**: Audit entries MUST NOT be changeable or removable from the admin area or by any
  automatic clean-up, and MUST survive the deletion of the accounts they name.
- **FR-018**: The admin area MUST show the audit log, newest first, naming accounts by email while
  they exist and by identifier after.

**Telemetry (User Story 3)**

- **FR-019**: The system MUST save request and AI-call telemetry with only the details already
  permitted for the logs (feature 008) and nothing else; database-level timings are not saved.
- **FR-020**: Saving telemetry MUST never slow down or fail a user's request.
- **FR-021**: Saved telemetry older than 30 days MUST be removed automatically.
- **FR-022**: The admin area MUST show a telemetry page: requests per day, the server-side failure
  share, the slowest pages (median and 95th-percentile time), AI calls per feature by outcome,
  AI call duration and tokens used per day.
- **FR-023**: Tests MUST be able to run without saving telemetry unless a test turns it on.

**General**

- **FR-024**: Nothing in this feature MAY call an AI model (constitution Principle I).
- **FR-025**: The admin area MUST be reachable at `/admin` in development and in the deployed app,
  with the deployed app's existing security headers kept.

### Key Entities

- **Admin account**: a staff account marked as admin, created from the command line, unable to use
  the taxpayer app.
- **Account status**: whether an account is disabled, and since when.
- **Audit entry**: which admin did what (viewed an account, disabled, re-enabled, deleted, signed
  out everywhere, reset the reading limit), to which account, and when. Never changed or removed.
- **Telemetry record**: one request or AI call: its kind, when it started, how long it took,
  whether it failed, and the permitted details. Kept 30 days.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can see any account's progress (profile, documents, tax result, guided
  step) within 3 clicks of signing in.
- **SC-002**: 100% of admin actions and account-detail views produce exactly one audit entry, and
  none produces one for list pages.
- **SC-003**: No admin page shows a password, session or token in any form (checked on every page).
- **SC-004**: Each of the four actions takes effect in the taxpayer app immediately after it
  completes (checked by signing in, using a session or token, and requesting a reading).
- **SC-005**: Deleting an account leaves no stored file of that account behind, in every test case
  including a storage outage.
- **SC-006**: Users notice no slowdown: pages respond as quickly with telemetry saving on as off,
  and no request fails because saving failed.
- **SC-007**: The telemetry page's figures match the recorded requests and AI calls exactly.

## Assumptions

- The people running the app are a small team; one admin role is enough for now (Saifullah:
  "A for now"); a read-only role can be added later.
- Document readings ("extractions") are the only AI use with a per-user daily limit; the Ask
  assistant's hourly per-user limit resets on its own, so it has no reset action.
- Resetting a reading limit also frees the same number of app-wide readings for the day (simplest;
  recorded in the audit log).
- The admin area uses its library's own look, not the taxpayer app's.
- All data is synthetic (constitution Principle V); the admin area adds no new kind of personal
  data.
- The deployed app runs one backend process, so one telemetry writer.
- Ships in the same pull request as the 004 bank-profit fix; the lead reviews spec and plan in it
  before merge, including the choice of library and the constitution amendment.
