# Contract: API conventions

Published as `docs/api-conventions.md`. Every feature's API contract follows these rules.

- **Paths:** all endpoints under `/api/`, grouped by area (`/api/auth/...`,
  `/api/documents/...`); plural nouns for collections; no verbs except for actions such as
  `/api/auth/login`.
- **Bodies:** JSON only (`Content-Type: application/json`); field names in `snake_case`;
  money as strings holding decimals (e.g. `"125000.00"`), never floats (Principle I); dates as
  ISO 8601.
- **Errors:** `{"detail": "<human-readable message>"}`. Status codes: `400` bad input that passed
  validation, `401` not logged in, `403` logged in but not allowed, `404` not found or not
  yours (never reveal that another user's item exists), `409` conflict, `422` validation
  error, `429` throttled.
- **Authentication:** the `session` cookie; protected endpoints use `current_user`
  (feature 002).
- **Keeping in step:** a change to an endpoint updates, in the same pull request, the feature's
  contract in `specs/NNN-*/contracts/`, the backend tests and the frontend code that calls it.
  FastAPI's OpenAPI schema at `/openapi.json` is the generated reference.
- **Machine-checkable contract (issue #16):** every route declares its `response_model`, and
  each feature's `contracts/api.yaml` lists its endpoints (path, method, success status,
  required request and response fields); `scripts/validate_contracts.py` checks the app against
  it. A change to an endpoint updates the Markdown contract and `api.yaml` together.
