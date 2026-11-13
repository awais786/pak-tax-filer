# Feature Specification: Document Upload + AI Extraction

**Feature Branch**: `003-document-extraction`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Document upload + AI extraction (README milestone 3). A logged-in user uploads a salary certificate or bank profit certificate (PDF, JPG or PNG; max 10 MB, 5 pages; user picks the type). The AI extracts only figures, each with a value, confidence and source location. Consistency rules downgrade fields to low confidence. The user confirms or edits each field, then confirms the document; only confirmed documents are usable by other features, enforced by the backend. An eval of 80 synthetic labelled files measures accuracy; the model is the cheapest that meets the bar." Source design: `docs/superpowers/specs/2026-11-03-document-extraction-design.md`.

## Clarifications

### Session 2026-11-03

- Q: Can a user have more than one confirmed certificate of the same type (e.g. two employers or two banks in the same year)? → A: Yes. Any number of confirmed certificates per type and tax year; the tax engine (feature 004) sums them, matching the README's "simple sum" of multiple employers.

### Session 2026-11-05

- Q: Can a certificate whose tax year differs from the profile's be confirmed (the rule check only flags it)? → A: No. Confirming is refused until the certificate's tax year equals the profile's, so a certificate for another year can never be counted in the profile's year. Confirmed amounts must also be non-negative, whether typed or extracted (found in code review).

### Session 2026-11-09

- Q: With open sign-up (feature 002, User Story 6) on a public site, how is the free AI quota protected? → A: Each user may start at most 10 extractions in any 24 hours (FR-017); uploads and retries both count, including files refused as the wrong type, since each one calls the AI. Because anyone can make more accounts, the whole app is also limited to 100 extractions in any 24 hours (added after code review).
- Q: The lead asked to keep uploaded files in Google Cloud Storage, privately ("buckets ... store them privately"); what changes? → A: In the deployed app, files go to a private bucket (public access prevented, reachable only with the server's own Google identity, no public links); users still get their files only through the owner-checked endpoint. Development and tests keep the local disk (FR-018, research R4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a certificate and get its figures (Priority: P1)

A logged-in user uploads their salary certificate or bank profit certificate, as a PDF from
their employer or bank or as a photo taken on their phone, says which type it is, and within
moments sees the figures the app found, each with how sure the app is and where on the page it
was found.

**Why this priority**: it is the core of the feature: without extraction there is nothing to
review.

**Independent Test**: upload one synthetic certificate of each type, as a PDF and as a photo;
each shows its fields with values, confidence and source location.

**Acceptance Scenarios**:

1. **Given** the upload page, **When** it loads, **Then** a "demo data only, do not upload real
   documents" notice is visible.
2. **Given** a PDF, JPG or PNG of at most 10 MB and 5 pages, **When** the user uploads it as a
   salary certificate, **Then** the app shows tax year, gross salary, taxable salary and tax
   deducted, each with a value (or "not found"), a confidence of high, medium or low, and the
   page and printed label it came from.
3. **Given** the same for a bank profit certificate, **Then** the app shows tax year, profit
   amount and tax withheld under §151 in the same way.
4. **Given** a file of another type, over 10 MB, or over 5 pages, **When** the user uploads it,
   **Then** it is refused with a message saying which limit was broken, and nothing is sent to
   the AI.
5. **Given** extracted values that break a consistency rule (an amount that isn't a valid
   non-negative number; tax deducted or taxable salary greater than gross salary; tax withheld
   greater than profit amount; a tax year not in the form 2025-26 or not equal to the tax
   year in the user's taxpayer profile), **When** results are shown, **Then** each field involved is shown as
   low confidence with the reason.
6. **Given** extraction is in progress, **When** the user waits, **Then** progress is shown
   until results appear.

---

### User Story 2 - Review, correct and confirm (Priority: P2)

The user checks each extracted figure against the document shown beside it, corrects anything
wrong, and confirms the document. Only then can other parts of the app use its figures.

**Why this priority**: human confirmation is a non-negotiable rule (constitution, Principle
III); extracted values are never trusted on their own.

**Independent Test**: upload a certificate, edit one value, confirm every field and the
document; check that the edited value is stored and that, before confirmation, the figures
could not be read by any other part of the app.

**Acceptance Scenarios**:

1. **Given** a document that needs review, **When** the user opens it, **Then** the document is
   shown beside its fields and low-confidence fields are highlighted.
2. **Given** a field, **When** the user edits its value, **Then** the new value is validated by
   the same rules and marked as entered by the user.
3. **Given** some fields are not yet confirmed, **When** the user tries to confirm the document,
   **Then** they are told which fields still need confirming.
4. **Given** every field is confirmed, **When** the user confirms the document, **Then** its
   status becomes confirmed and its values can no longer be edited.
5. **Given** a document that is not confirmed, **When** any other part of the app asks for its
   figures, **Then** it is refused.

---

### User Story 3 - Manage my documents (Priority: P3)

The user sees a list of their uploaded documents with each one's type and status, can retry a
failed extraction, and can delete a document they no longer want.

**Why this priority**: useful housekeeping, but Stories 1 and 2 deliver the value.

**Independent Test**: upload two documents, make one extraction fail, retry it, delete the other,
and check that the list and stored files match.

**Acceptance Scenarios**:

1. **Given** a user with documents, **When** they open their document list, **Then** each shows
   its type, upload time and status (uploaded, extracting, needs review, confirmed, failed).
2. **Given** a failed extraction, **When** the user retries it, **Then** extraction runs again.
3. **Given** any document, **When** the user deletes it, **Then** the document, its figures and
   its stored file are removed.
4. **Given** users A and B, **When** B tries to see, change, confirm or delete A's document,
   **Then** it is refused and nothing about A's document is revealed.

---

### User Story 4 - Measure extraction accuracy (Priority: P4)

A developer runs the extraction eval to learn how accurate extraction is on clean PDFs and on
photos, how often wrong values are marked high confidence, and which AI model is the cheapest
that meets the accuracy bar.

**Why this priority**: required by the constitution (Principle VI) before relying on
extraction, but invisible to users.

**Independent Test**: run the eval; it processes all 80 files and reports the measures below for
each model tried.

**Acceptance Scenarios**:

1. **Given** the eval set, **When** the eval runs, **Then** it reports per-field accuracy
   separately for clean PDFs and photos, and the share of wrong values that were marked high
   confidence.
2. **Given** results, **When** compared with the bar (at least 95% of fields correct on PDFs, at
   least 90% on photos, at most 2% of wrong values marked high confidence), **Then** the eval
   passes or fails clearly.
3. **Given** a change to extraction, **When** it is proposed for merge, **Then** the proposal
   includes a passing eval result, and the eval runs again automatically once merged; a failure
   is visible and must be fixed.

### Edge Cases

- A field isn't on the document: shown as "not found" with low confidence; the user must enter
  it or mark it as zero before confirming.
- The user picked the wrong document type: most fields come back "not found" or low confidence;
  the user deletes the document and uploads it again with the right type.
- The AI service is unavailable, times out or declines the request: the document is marked
  failed with a short reason and can be retried; nothing partial is saved as extracted.
- A password-protected or unreadable PDF: refused at upload with a message.
- A multi-page document where figures appear on page 2 or later: the source location shows the
  right page.
- Two uploads of the same file: both are kept as separate documents; the document list shows
  both so the user can delete the duplicate (otherwise its figures would be counted twice).
- Several employers or banks in one year: the user uploads and confirms one certificate for
  each; all confirmed certificates count.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Logged-in users MUST be able to upload a PDF, JPG or PNG of at most 10 MB and 5
  pages, choosing its type: salary certificate or bank profit certificate.
- **FR-002**: Files breaking those limits, password-protected or unreadable MUST be refused
  before extraction, with a message naming the problem.
- **FR-003**: For a salary certificate, the system MUST extract tax year, gross salary, taxable
  salary and tax deducted; for a bank profit certificate, tax year, profit amount and tax
  withheld under §151. No other information MUST be extracted or stored from the document.
- **FR-004**: Each extracted field MUST have a value or "not found", a confidence of high,
  medium or low, and its source location (page and printed label).
- **FR-005**: Fields that break a consistency rule (listed in User Story 1, scenario 5) MUST be
  set to low confidence, with the reason shown.
- **FR-005a**: If the uploaded document is not the type the user chose (e.g. a bank profit
  certificate uploaded as a salary certificate), the upload MUST be refused with a message saying it
  doesn't look like the chosen type, naming what it may be only as a hint (the AI's guess could
  be wrong), and asking the user to check the file and type; nothing is saved, and the
  user stays on the upload page with their file and type still chosen. Only a document that is
  ready to review opens the review page; any other failed extraction keeps the user on the upload
  page with the reason, the document listed with Retry. *(Added 2026-11-09 after manual
  testing.)*
- **FR-006**: Amounts MUST be stored exactly, never as approximate numbers (constitution,
  Principle I).
- **FR-007**: Users MUST be able to edit any field before confirmation; edited values MUST pass
  the same rules and be marked as user-entered.
- **FR-008**: A document MUST only become confirmed once every field is confirmed, every amount
  is non-negative and its tax year equals the tax year in the user's profile; confirmed
  documents MUST NOT be editable.
- **FR-009**: Figures from a document that is not confirmed MUST NOT be available to any other
  part of the system, enforced by the backend.
- **FR-010**: Documents MUST move through the statuses uploaded, extracting, needs review,
  confirmed, or failed; failed extractions MUST be retryable.
- **FR-010a**: A user MAY have any number of confirmed certificates of each type for the same
  tax year; none replaces another.
- **FR-011**: Users MUST be able to list their documents and delete any of them, which removes
  its figures and stored file.
- **FR-012**: Only the owning user MUST be able to see or act on a document.
- **FR-013**: The upload page MUST show a clear "demo data only" notice.
- **FR-014**: A labelled eval set of 80 synthetic files (20 per type, each as a clean PDF and a
  photo-like image, across at least 4 layouts per type) MUST exist, with a way to run it that
  reports per-field accuracy for PDFs and photos and the share of wrong values marked high
  confidence.
- **FR-015**: Every proposed change to extraction MUST include a passing eval result; the eval
  MUST run automatically after merge and be runnable on demand. (It can't run automatically
  before merge on proposals from a fork, because the API key can't be shared with them; if the
  developer is given branch access to the main repository, it MUST also run before merge.)
- **FR-016**: The AI model used MUST be a setting, chosen as the cheapest that meets the bar.
- **FR-017**: Each user MUST be limited to 10 extraction attempts (uploads and retries that
  call the AI) in any 24 hours, and the whole app to 100. Over a limit, the request MUST be
  refused before the AI is called or any file is stored, with "Daily limit reached: 10
  extractions per 24 hours. Try again later." or "The app's daily extraction limit has been
  reached. Try again later." (added 2026-11-09). A try lost to Google's side (a server error,
  such as its 504 after the 60-second deadline, or no connection) MUST NOT count: the document
  is kept as failed, and its reason says the AI service is busy (or couldn't be reached), to
  press Retry in a minute, and that the try didn't count (amended 2026-11-13, after the lead's
  uploads failed this way on the live site on 2026-11-12). A refusal of the file itself
  (unreadable, wrong type) still counts, since Google answered.
- **FR-018**: Where a storage bucket is configured, uploaded files MUST be stored in it and
  nowhere else; the bucket MUST be private (no public access, no public links), and files MUST
  reach users only through the owner-checked file endpoint. Without a bucket (development,
  tests), files are stored on the local disk. Files stored before a bucket was configured MUST
  stay readable and deletable (added 2026-11-09).

### Key Entities

- **Document**: an uploaded certificate. Owner, type, original file, page count, status, upload
  time, and failure reason if failed.
- **Extracted field**: one figure from a document. Field name, value or "not found", confidence,
  source page and label, consistency-rule reason if downgraded, whether user-edited, and whether
  confirmed.
- **Eval case**: one synthetic file with its correct values, type, layout and whether it is a
  clean PDF or photo.
- **Extraction attempt**: one call to the AI for a user's document, with its time; kept only to
  enforce the daily limit (FR-017).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user sees extracted figures within 30 seconds of uploading a 1-page certificate.
- **SC-002**: A user can review and confirm a certificate in under 2 minutes.
- **SC-003**: On the eval set, at least 95% of fields are correct on clean PDFs and at least 90%
  on photos.
- **SC-004**: At most 2% of wrong values are marked high confidence.
- **SC-005**: 100% of attempts to read unconfirmed figures from elsewhere in the system are
  refused in testing.
- **SC-006**: 100% of attempts by one user to access another user's documents are refused in
  testing.

## Assumptions

- Builds on features 001 (running app, CI) and 002 (logged-in users).
- Synthetic documents only (constitution, Principle V); no real certificates are uploaded,
  stored or used in the eval.
- The tax year comes from the user's taxpayer profile (feature 002; today only 2025-26). A user
  without a profile cannot upload; the app sends them to set it up first (amended 2026-11-04).
- An API key with credits is available for development, testing and the automated eval
  (pending from the lead).
- Known limitation: synthetic certificates can't reproduce the variety of real ones, so eval
  results may overstate real-world accuracy; they must be re-checked against consented,
  anonymised real documents once legal review allows.
- Passing figures to the tax engine is feature 004's job; it reads confirmed documents only and
  sums all confirmed certificates of each type.
