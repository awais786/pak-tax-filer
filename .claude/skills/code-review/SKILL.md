---
name: "code-review"
description: "Review a pak-tax-filer change before it is committed or merged: architecture, security, business logic, test coverage, regressions. Use when asked to review code, a diff or a pull request."
---

# Review a change

1. **Scope.** Read the diff (`git diff`, or the PR) and the task it implements in
   `specs/NNN-*/tasks.md`, with its spec and contract.
2. **Delegate by area.** Use the `backend-reviewer` subagent for `backend/` changes and the
   `frontend-reviewer` subagent for `frontend/` changes; review anything else yourself.
3. **Checklist** (lead's issue #4, rule 5); for each, note pass or the specific problem:
   - **Architecture:** matches the plan and folder guides; logic outside routers/components.
   - **Security:** no secrets, tokens or personal data in code, logs, tests or commits; auth on
     protected endpoints; `404` for other users' items.
   - **Business logic:** tax and reconciliation maths are deterministic `Decimal` code, never an
     LLM (Principle I); rates only from FBR with sources (II); confirmed data only (III);
     labels and citations (IV).
   - **Tests:** every behaviour in the change has a test that would fail without it; tests ran.
   - **Regressions:** existing tests, lint, format and type checks still pass; contracts still
     match.
4. **Report** findings ranked by severity, each with file and line and a suggested fix. Do not
   edit code while reviewing.
