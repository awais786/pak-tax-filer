# End-to-end tests with Playwright: design

2026-11-13. Requested by the lead (Awais, 2026-11-12: "Playwright is a testing tool and its
purpose is to test the application; you should add some e2e tests also"), after his uploads
failed on the live site.

## Intent

Drive the real app in a real browser, the way a user does, so a broken main flow ("upload isn't
working") is caught in CI before anyone sees it. The unit and API tests check the parts; nothing
today checks that the pages, the API, the database and the AI clients work together.

**Goals:** the main flows pass in Chromium against the Docker stack, locally and in CI, with no
real AI and no real data. **Non-goals:** every page and edge case (the unit and API tests cover
those), other browsers, visual comparison, load. **Anti-goals:** a flaky suite; tests that call
real Gemini (quota, Principle VI's "tests never call the real AI"); a test switch inside the app.

## Approaches (the user chose B)

| | Approach | Trade-off |
|---|---|---|
| A | An `AI_MODE=fake` setting in the backend, on only in an e2e compose file | Quickest; but a test switch in production code, needing a guard |
| **B** | **A fake Gemini server in the e2e stack; the app's real clients point at it** | **No test code in the app, and the real clients are exercised; more work to give believable answers** |
| C | Only flows without AI | Skips upload → confirm → tax, the flow that broke |

B works without changing the app: the google-genai SDK reads `GOOGLE_GEMINI_BASE_URL` from the
environment (checked in google-genai 3.0.0, `_base_url.py`).

## Design

- **A fake Gemini server** (`e2e/fake_gemini/server.py`, standard library only) stands in for
  Google; the app's real clients reach it through `GOOGLE_GEMINI_BASE_URL`. It recognises a
  request by its structure, never by prompt wording, and fakes only what a test needs. What it
  answers is described once, in `server.py`'s docstring (and summarised in `e2e/README.md`).
- **`docker-compose.e2e.yml`** adds it to the development stack, under its own project name
  (`-p pak-e2e`, so its own database) and its own ports (18000, 15173), so it runs beside
  development.
- **`e2e/`**: Playwright, Chromium only. Every test signs up its own user and makes its own
  synthetic PDF (Principle V). One test drives the whole path through the UI (sign up → upload →
  confirm → tax → PDF); the others set that up through the API and test only their own page, so a
  change to one screen fails one test.
- **CI:** a job `e2e` with a time limit, failing clearly if the stack never starts, no retries
  (a flaky test must show), and the report and logs attached when a test fails.

## Decided by the builder (my calls)

Chromium only; a standard-library fake (no new dependency) with fixed answers; the "Google
busy" path triggered by a marker inside the synthetic PDF, since the browser can't send the
fake a header.

## Revised after review (PR #44, 2026-11-13)

No retries in CI; a time limit and clear failures for the stack's start; API set-up for the tests
that don't test the upload; unused fake answers removed; separate ports; this doc trimmed to
intent and decisions so it can't drift from the code.
