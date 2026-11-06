# Frontend guide (React + TypeScript, Vite)

Loaded when working in `frontend/`. The root `CLAUDE.md` and `.claude/rules/` still apply.

## Layout

- `src/main.tsx`: mounts the app; `src/App.tsx`: the top-level component.
- `src/pages/<Name>Page.tsx`: one file per page, with `<Name>Page.test.tsx` beside it.
- `src/components/`: shared components; `src/api/`: the single helper for calling the backend.

## Adding a page

1. Check the feature's contract in `specs/NNN-*/contracts/` for the endpoints it uses.
2. Write the failing test (`*.test.tsx`, React Testing Library, find elements by role or text
   as a user would); run `npm test` and see it fail.
3. Build the page; call the backend only through the helper in `src/api/` (one place for the
   base path, JSON and errors), never `fetch` directly in components.
4. Run `npm test`, `npm run lint`, `npx tsc -b`, `npx prettier --check .`.

## Notes

- Money arrives from the API as decimal strings; display it as text, never do tax maths here
  (constitution, Principle I).
- In Docker the app runs on `http://localhost:5173`; tests run with
  `docker compose exec frontend npm test` or `npm test` on the host.
