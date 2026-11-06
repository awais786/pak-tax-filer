# API Conventions

- Follow `docs/api-conventions.md` for every endpoint: paths under `/api/`, JSON in
  `snake_case`, money as decimal strings, `{"detail": ...}` errors and the standard status
  codes, session-cookie authentication.
- The feature's contract in `specs/NNN-*/contracts/` is the source of truth: change the
  contract, the backend tests and the frontend caller in the same pull request as the endpoint.
- Never reveal whether another user's item exists: answer `404` for "not found or not yours".
