# Testing & Code Quality

- Write or update tests for the behavior you change; don't leave a feature
  untested because "it's simple."
- Run the project's actual test suite and linters before calling a task
  done — report what you actually ran and what actually happened, never an
  assumed or expected result.
- A PostToolUse hook runs pylint on Python files and the frontend's own
  `lint` script on JS/TS files when those tools exist in the project; treat
  its findings as real feedback to fix, not noise to ignore.
- Don't mark a task complete with a known-failing test or lint error left
  unexplained.
- Write the failing test first and watch it fail for the right reason before writing the code
  (constitution, Principle VI).
- Backend tests that need a database use the separate test database, never development data.
