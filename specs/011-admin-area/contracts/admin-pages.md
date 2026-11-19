# Contract: Admin Pages (011)

Server-rendered pages mounted at `/admin` (starlette-admin, research R1). They are not part of the
JSON API: `docs/api-conventions.md` doesn't apply, and they don't appear in the OpenAPI schema or
an `api.yaml`. This file is what the tests check.

## Access

| Who | Gets |
|---|---|
| Not signed in to the admin area | Every admin page redirects to `/admin/login` |
| Active admin account | Every page below |
| Taxpayer account, wrong password, disabled account, unknown email | `/admin/login` shows one message: "Invalid email or password." (the app's own wording, the same for all) |
| More than 10 failed admin sign-ins for one email in 15 minutes | "Too many attempts. Try again later." (feature 002's numbers; counted under a key the public login can't produce, a space then `admin:` + email (review M3); emails or passwords over 254/1024 characters are refused before anything is stored (review M2)) |

**Session cookie** `admin_session`: `HttpOnly`; `Secure` unless `COOKIE_SECURE=false`;
`SameSite=Strict`; `Path=/admin`; max age 8 hours; the value is a random token whose SHA-256 is
stored in `sessions`. Sign-out (a POST to `/admin/logout` with the CSRF token) deletes the session and
clears the cookie. The login form labels the email field "Username" (the library's page; research R13).

**Forms** carry the library's CSRF token (signed with `ADMIN_SECRET_KEY`, research R3).

## Pages

| Page | Path (library's) | Shows | Allowed |
|---|---|---|---|
| Dashboard | `/admin/` | FR-006's counts | view |
| Accounts | `/admin/account/list` | email, created, admin, disabled; search by email | view; the four actions on taxpayer rows |
| Account | `/admin/account/detail?pk=…` | email, created, admin, disabled; tax year and ATL; documents (type, status, tax year, uploaded); Tax result (figures or refusal reason, from 004); guided-run step as stored | view (writes one `view_account` audit entry); the four actions on a taxpayer account |
| Documents | `/admin/document/list` | type, status, tax year, uploaded, owner email | view (no detail page, no file) |
| Law library | `/admin/corpus-document/list` | each corpus document with its passage count | view |
| Telemetry | `/admin/telemetry` | FR-022's figures, last 30 days | view |
| Audit log | `/admin/audit-log/list` | newest first: at, admin, action, account (email while it exists, else id) | view |

The exact path segments are the library's identities for each view; the tests read them from the
running app rather than hard-coding more than the table above.

**Never offered on any page:** create, edit, delete (other than the delete-account action), export,
import, the uploaded files. **Never shown:** `password_hash`, any session or token hash, question
text.

## Actions (accounts list and account page; taxpayer accounts only)

| Action | Confirmation | Effect | Audit |
|---|---|---|---|
| Disable | "Disable this account? The user is signed out and can't sign in." | FR-014(a) | `disable` |
| Re-enable (shown instead of Disable when disabled) | "Re-enable this account?" | FR-014(b) | `enable` |
| Delete account | "Delete this account and all its data? This can't be undone." | FR-014(c); on a storage outage: "Storage can't be reached; nothing was deleted. Try again later." | `delete_account` (on success only) |
| Sign out everywhere | "Sign this user out on every device?" | FR-014(d) | `sign_out_everywhere` |
| Reset reading limit | "Clear this user's document readings from the last 24 hours?" | FR-014(e) | `reset_reading_limit` |

None of the actions is offered for an admin account.

## Command line

```
python -m app.cli create-admin --email admin@example.com
```

Prompts for the password twice (as `create-user`); an admin password needs at least 12 characters
(taxpayers' stay 8; added after review L5). Refuses an email that already has an account
("A user with that email already exists.", as `create-user`), never promotes a taxpayer account. Exit 0 on
success, 1 on refusal.

## Effect on the taxpayer app (feature 002 and 006 contracts, unchanged in shape)

- `POST /api/auth/login` with an admin or disabled account → `401` "Invalid email or password."
  (the existing message).
- Any endpoint using `current_user` with an admin's or a disabled account's session → `401`
  "Not logged in." (the existing message).
- MCP tools with an admin's or a disabled account's token → refused as an invalid token.
