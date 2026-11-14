# API conventions

Every feature's API contract (`specs/NNN-*/contracts/`) and every backend endpoint follow these
rules. Source: [specs/001-repo-foundations/contracts/api-conventions.md](../specs/001-repo-foundations/contracts/api-conventions.md).

- **Paths:** all endpoints under `/api/`, grouped by area (`/api/auth/...`,
  `/api/documents/...`); plural nouns for collections; no verbs except for actions such as
  `/api/auth/login`. The one exception is the infrastructure probe `GET /health`
  ([health.md](../specs/001-repo-foundations/contracts/health.md)), which sits at the root as health checks conventionally do.
- **Bodies:** JSON only (`Content-Type: application/json`); field names in `snake_case`;
  money as strings holding decimals (e.g. `"125000.00"`), never floats (Principle I); dates as
  ISO 8601.
- **Errors:** `{"detail": "<human-readable message>"}`. Status codes: `400` bad input that passed
  validation, `401` not logged in, `403` logged in but not allowed, `404` not found or not
  yours (never reveal that another user's item exists), `409` conflict, `415` not JSON on a
  state-changing request, `422` validation error, `429` throttled. A `422` keeps FastAPI's list of field errors
  (`loc`, `msg`, `type`) but never echoes the rejected value (`input`), which could be a
  password or personal data.
- **Authentication:** the `session` cookie; protected endpoints use `current_user`
  (feature 002).
- **Keeping in step:** a change to an endpoint updates, in the same pull request, the feature's
  contract in `specs/NNN-*/contracts/`, the backend tests and the frontend code that calls it.
  FastAPI's OpenAPI schema at `/openapi.json` is the generated reference.
- **Machine-checkable contract (issue #16):** every route declares its response model (a
  Pydantic return type or `response_model=`), and each feature's `contracts/api.yaml` lists its
  endpoints (path, method, success status, required request and response fields);
  `scripts/validate_contracts.py` checks the app against it (`docs/contracts.md`). A change to an
  endpoint updates the Markdown contract and `api.yaml` together.
