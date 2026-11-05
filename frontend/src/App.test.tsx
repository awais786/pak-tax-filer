import { render, screen } from "@testing-library/react";
import { test } from "vitest";
import App from "./App";

// Fails if the placeholder page has no top-level heading naming the app, or no
// "under construction" line (spec FR-004, tasks T011/T013). getBy* queries throw when
// nothing matches, so they are the assertions.
test("the placeholder page names the app and says it is under construction", () => {
  render(<App />);

  screen.getByRole("heading", { level: 1, name: /pak-tax-filer/i });
  screen.getByText(/under construction/i);
});

// Checks the cleanup in test-setup.ts: without it, the first test's page would still be
// mounted and this query would find two headings and throw.
test("each test starts with an empty page", () => {
  render(<App />);

  screen.getByRole("heading", { level: 1, name: /pak-tax-filer/i });
});
