import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Protected home page and logout (task T024, FR-012, FR-013).

const ME = { status: 200, body: { email: "demo@example.com" } };
const NOT_LOGGED_IN = { status: 401, body: { detail: "Not logged in." } };

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a logged-out visitor is sent to the login page", async () => {
  mockFetch({ "GET /api/auth/me": () => NOT_LOGGED_IN });
  renderApp("/");

  await screen.findByRole("heading", { name: /log in/i });
});

test("a logged-in user sees their email and a logout button", async () => {
  mockFetch({ "GET /api/auth/me": () => ME, "GET /api/profile": hasProfile });
  renderApp("/");

  await screen.findByText(/logged in as demo@example\.com/i);
  screen.getByRole("button", { name: /log out/i });
});

test("logging out returns to the login page", async () => {
  let loggedIn = true;
  mockFetch({
    "GET /api/auth/me": () => (loggedIn ? ME : NOT_LOGGED_IN),
    "GET /api/profile": hasProfile,
    "POST /api/auth/logout": () => {
      loggedIn = false;
      return { status: 204 };
    },
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));

  await screen.findByRole("heading", { name: /log in/i });
});

test("a session that ended elsewhere sends the user to login with a message", async () => {
  // The app's first check finds a session; it has ended by the time the page asks again.
  let calls = 0;
  mockFetch({
    "GET /api/auth/me": () => (++calls === 1 ? ME : NOT_LOGGED_IN),
    "GET /api/profile": hasProfile,
  });
  renderApp("/");

  await screen.findByText(/your session has ended, please log in again\./i);
  screen.getByRole("heading", { name: /log in/i });
});

test("logging out really ends the session on the server", async () => {
  let loggedIn = true;
  const fake = mockFetch({
    "GET /api/auth/me": () => (loggedIn ? ME : NOT_LOGGED_IN),
    "GET /api/profile": hasProfile,
    "POST /api/auth/logout": () => {
      loggedIn = false;
      return { status: 204 };
    },
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));
  await screen.findByRole("heading", { name: /log in/i });

  const logouts = fake.mock.calls.filter(
    ([url, init]) =>
      String(url) === "/api/auth/logout" && init?.method === "POST",
  );
  expect(logouts).toHaveLength(1);
});

test("a failed logout says so instead of pretending it worked", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/auth/logout": () => ({
      status: 500,
      body: { detail: "Server error." },
    }),
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Couldn't log out, try again.",
  );
  screen.getByText(/logged in as demo@example\.com/i);
});

test("a logged-out visitor sees no 'session ended' message", async () => {
  mockFetch({ "GET /api/auth/me": () => NOT_LOGGED_IN });
  renderApp("/");

  await screen.findByRole("heading", { name: /log in/i });
  expect(screen.queryByText(/session has ended/i)).toBeNull();
});
