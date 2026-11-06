---
paths:
  - "frontend/**"
---

# Frontend Conventions (React + TypeScript)

- Function components and hooks; one page per file in `src/pages/`, its test beside it.
- Call the backend only through the helper in `src/api/`; never `fetch` directly in components.
- Money arrives as decimal strings: display it, never calculate with it (Principle I).
- Tests use React Testing Library and find elements as a user would (role, label, text), not by
  CSS classes or test ids.
- Keep TypeScript strict; no `any` without a comment explaining why.
- Show the "not yet practitioner-reviewed" label wherever a tax or wealth result appears
  (Principle IV).
