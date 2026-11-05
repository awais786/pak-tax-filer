---
name: "react-feature"
description: "Add a frontend page or component to pak-tax-filer: contract check, failing test, React code through the API helper, checks. Use when building or changing frontend UI."
---

# Add a React feature slice

Follow `frontend/CLAUDE.md`, `.claude/rules/frontend.md`, `.claude/rules/api.md` and the
constitution. Work on the feature's task in `specs/NNN-*/tasks.md`.

1. **Contract.** Read the endpoints the page uses in `specs/NNN-*/contracts/`.
2. **Failing test.** Write `src/pages/<Name>Page.test.tsx` (or the component's test) with React
   Testing Library, finding elements by role, label or text. Run `npm test` and confirm it fails
   for the right reason.
3. **Code.** Build the page in `src/pages/`; call the backend only through `src/api/`. Display
   money as given (decimal strings); no tax maths in the frontend (Principle I). Show the
   "not yet practitioner-reviewed" label on any tax or wealth result (Principle IV).
4. **Checks:** `npm test`, `npm run lint`, `npx tsc -b`, `npx prettier --check .`. Report what
   actually ran and its result.
5. Tick the task in `tasks.md`, and show the diff for review before committing.
