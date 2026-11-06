import { screen } from "@testing-library/react";
import { afterEach, test, vi } from "vitest";
import { mockFetch } from "./test/mockFetch";
import { renderApp } from "./test/renderApp";

// Routing (task T029): 001's placeholder page is replaced by the login and home pages.

const LOGGED_OUT = {
  "GET /api/auth/me": () => ({
    status: 401,
    body: { detail: "Not logged in." },
  }),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("/login shows the login page", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/login");

  await screen.findByRole("heading", { level: 1, name: /log in/i });
});

// Checks the cleanup in test-setup.ts: without it, the previous test's page would still be
// mounted and this query would find two "Log in" headings and throw.
test("each test starts with an empty page", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/login");

  await screen.findByRole("heading", { level: 1, name: /log in/i });
});

test("an unknown address shows a not-found page with a way home (PR #27 review, item 5)", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/no-such-page");

  await screen.findByRole("heading", { level: 1, name: /page not found/i });
  screen.getByRole("link", { name: /home/i });
});
