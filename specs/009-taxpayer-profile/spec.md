# Feature Specification: Taxpayer Profile

**Feature Branch**: `009-taxpayer-profile`

**Created**: 2026-11-04

**Status**: Draft

**Input**: README MVP item "One taxpayer profile, one configurable tax year (TY2026)"; roadmap
milestone 2 increment ("the taxpayer profile (tax year, ATL status) … must exist before 007").
Source design: `docs/superpowers/specs/2026-11-04-taxpayer-profile-design.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Set up the profile on first login (Priority: P1)

A logged-in user who has no profile yet is taken to a short "set up your profile" step before
anything else. They choose the tax year (only 2025-26 is offered) and say whether they are on
FBR's Active Taxpayers' List (ATL), with a link to FBR's online ATL check beside the question. A
one-line notice says the app covers people who live in Pakistan and earn a salary. After saving,
they reach the app.

**Why this priority**: the tax calculation and the later agentic workflow (007) need the tax year
and ATL status; without a profile nothing downstream can run.

**Independent Test**: create a demo user, log in, check that every other page leads back to the
setup step until it is saved, save it, and check that the app opens and the saved answers are
shown when the profile is reopened.

**Acceptance Scenarios**:

1. **Given** a logged-in user with no profile, **When** they open any page of the app, **Then**
   they are taken to the setup step.
2. **Given** the setup step, **When** it is shown, **Then** it offers tax year 2025-26 as the only
   choice, asks ATL status as yes or no with a link to FBR's online ATL check, and shows the
   residency notice.
3. **Given** the setup step, **When** the user tries to save without answering ATL status,
   **Then** saving is refused with a message asking for the answer.
4. **Given** both answers, **When** the user saves, **Then** the profile is stored and the user
   reaches the app.
5. **Given** a user with no profile, **When** any request that needs the profile is sent to the
   backend directly (not through the app's pages), **Then** it is refused or blocked with a
   message pointing to the profile, as described in FR-009 to FR-012.

---

### User Story 2 - Change the profile later (Priority: P2)

A user whose ATL status changes opens their profile, changes the answer and saves. The next tax
calculation uses the new answer.

**Why this priority**: ATL status can change during the year, and a stale answer gives a wrong
result; but it matters only after a profile exists.

**Independent Test**: with a saved profile, change ATL status, reopen the profile, and check the
new answer is shown; check that nothing else the user saved changed.

**Acceptance Scenarios**:

1. **Given** a saved profile, **When** the user opens the profile page from the app, **Then**
   their current answers are shown and can be changed.
2. **Given** the user changes ATL status and saves, **When** they next view their tax result,
   **Then** it is calculated with the new answer.
3. **Given** a change is saved, **When** the user looks at their uploaded documents and saved
   wealth statement, **Then** nothing has been deleted or altered.

---

### User Story 3 - Earlier features use the profile (Priority: P3)

Once document upload (003), the tax engine (004), the wealth statement (005) and the assistant's
tools (006) are built, they take the tax year and ATL status from the profile instead of asking
for them or using a fixed setting.

**Why this priority**: removes the stopgaps those features use until the profile exists (004:
"ATL status is asked on the tax page until the taxpayer-profile increment exists"); it can only
be done after they are built.

**Independent Test**: with 003–006 built and a saved profile, upload a certificate, open the tax
page and the wealth statement, and call the assistant's calculation tool; check each uses the
profile's tax year and ATL status and that the tax page no longer asks ATL.

**Acceptance Scenarios**:

1. **Given** a saved profile, **When** a certificate is uploaded, **Then** the upload is recorded
   against the profile's tax year, and a certificate whose tax year differs is flagged by 003's
   existing consistency check.
2. **Given** a saved profile, **When** the user opens the tax page, **Then** no ATL question is
   shown and the result uses the profile's ATL status.
3. **Given** a saved profile, **When** the user opens the wealth statement, **Then** it opens on
   the profile's tax year.
4. **Given** a saved profile, **When** the assistant's calculation tool is called with the user's
   access token, **Then** it uses the token owner's tax year and ATL status and takes no ATL or
   tax-year input; **and** the salary-check tool compares the certificate's tax year with the
   profile's.

---

### Edge Cases

- A user logs out from the setup step: allowed; the step appears again at the next login.
- A tax year other than 2025-26 is submitted (e.g. by editing the request): refused.
- The session expires while the setup step is open: saving fails like any expired session and
  the user is sent to log in again (002's behaviour).
- An assistant access token belongs to a user with no profile: the calculation tool returns the
  "tell us your ATL status" block with a pointer to the profile, not a result.
- The user saves the profile without changing anything: allowed, nothing changes.
- Two saves arrive close together (e.g. two tabs): the last one saved wins; there is still one
  profile.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each account MUST have at most one profile.
- **FR-002**: A profile MUST hold exactly two answers, both required: tax year and ATL status
  (yes or no). There MUST be no "not sure" option.
- **FR-003**: The only tax year offered and accepted MUST be 2025-26 (TY2026); the list of
  offered years MUST come from the same place as the years the tax engine supports, so adding a
  year later adds it to the profile choice.
- **FR-004**: The profile MUST NOT hold any identity field (name, CNIC, NTN or similar) or a
  residency answer (Principle V).
- **FR-005**: The setup step MUST show a link to FBR's official online ATL check beside the ATL
  question, and the notice "This app covers people who live in Pakistan and earn a salary".
- **FR-006**: A logged-in user with no profile MUST be taken to the setup step from every page of
  the app except logout.
- **FR-007**: A user MUST be able to view and change their profile at any time from the app.
- **FR-008**: Saving a profile MUST NOT change, recalculate or delete anything else the user has
  saved; a change applies from the next calculation.
- **FR-009**: The backend MUST enforce the profile, not only the app's pages: requests that need
  the profile from a user without one MUST be refused or blocked as in FR-010 to FR-012.
- **FR-010** *(follow-up to 003, once built)*: uploads MUST be recorded against the profile's
  tax year, 003's tax-year consistency rule MUST compare against it, and an upload from a user
  with no profile MUST be refused with "Set up your profile first".
- **FR-011** *(follow-up to 004, once built)*: the tax calculation MUST read ATL status from the
  profile; the tax page's ATL question and the ATL request input MUST be removed; with no profile
  the result MUST stay blocked with the existing "tell us your ATL status" reason, its message
  pointing to the profile.
- **FR-012** *(follow-up to 006, once built)*: the assistant's calculation tool MUST take tax year
  and ATL status from the token owner's profile and accept no ATL or tax-year input; the
  salary-check tool MUST compare the certificate's tax year with the profile's.
- **FR-013** *(follow-up to 005, once built)*: the wealth statement MUST open on the profile's
  tax year.
- **FR-014**: The profile MUST be visible and changeable only by its own account.

### Key Entities

- **Taxpayer profile**: belongs to one account (one-to-one); tax year (one of the supported
  years, today only 2025-26); ATL status (yes/no); when it was created and last changed. No
  identity fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user completes the setup step and reaches the app in under 1 minute.
- **SC-002**: In tests, 100% of the app's pages lead a user without a profile to the setup step,
  and 100% of backend requests that need the profile are refused or blocked without one.
- **SC-003**: After a change of ATL status, the next tax result uses the new answer in 100% of
  test cases.
- **SC-004**: Saving or changing a profile leaves every other saved record unchanged (verified by
  test).
- **SC-005**: Once 003–006 are built, no screen or tool asks for ATL status or tax year anywhere
  except the profile.
- **SC-006**: The stored profile contains no identity or residency data (verified by reviewing
  the data model and a test).

## Assumptions

- Builds on 002 (accounts, login, sessions, protected pages and APIs); demo users are created by
  002's developer command, so "first login" is the first login after that.
- 003–006's documents are not edited; FR-010 to FR-013 are follow-up work in this feature,
  carried out after those features are built. Until then, 004 keeps asking ATL on the tax page.
- 007 (agentic workflow) reads the profile; that is specified in 007.
- Only people who live in Pakistan and earn a salary are in scope (README); non-residents are
  outside the MVP, so residency is a notice, not a question.
- The link to FBR's online ATL check is a plain external link; the app does not look up ATL
  status itself.
- Synthetic/demo data only (Principle V).
