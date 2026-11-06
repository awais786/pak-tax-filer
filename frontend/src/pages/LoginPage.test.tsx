import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Login page, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T023, FR-012, FR-014).

const LOGGED_OUT = {
  "GET /api/auth/me": () => ({
    status: 401,
    body: { detail: "Not logged in." },
  }),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function submitLogin(email: string, password: string) {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: password },
  });
  fireEvent.click(screen.getByRole("button", { name: /log in/i }));
}

test("shows the demo-data notice and that password reset isn't available yet", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/login");

  await screen.findByRole("heading", { name: /log in/i });
  screen.getByText(/demo data only/i);
  screen.getByText(/password reset isn't available yet/i);
});

test("a successful login goes to the page named in next", async () => {
  let loggedIn = false;
  mockFetch({
    "GET /api/auth/me": () =>
      loggedIn
        ? { status: 200, body: { email: "demo@example.com" } }
        : { status: 401, body: { detail: "Not logged in." } },
    "GET /api/profile": hasProfile,
    "POST /api/auth/login": () => {
      loggedIn = true;
      return { status: 200, body: { email: "demo@example.com" } };
    },
  });
  renderApp("/login?next=/");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "demo-pass-123");

  await screen.findByText(/logged in as demo@example\.com/i);
});

test("a wrong password shows the server's message", async () => {
  mockFetch({
    ...LOGGED_OUT,
    "POST /api/auth/login": () => ({
      status: 401,
      body: { detail: "Invalid email or password." },
    }),
  });
  renderApp("/login");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "wrong-pass-1");

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Invalid email or password.",
  );
});

test("too many attempts shows the throttling message", async () => {
  mockFetch({
    ...LOGGED_OUT,
    "POST /api/auth/login": () => ({
      status: 429,
      body: { detail: "Too many attempts. Try again later." },
    }),
  });
  renderApp("/login");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "demo-pass-123");

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Too many attempts. Try again later.",
  );
});

test("opening the login page while logged in goes to the home page", async () => {
  mockFetch({
    "GET /api/auth/me": () => ({
      status: 200,
      body: { email: "demo@example.com" },
    }),
    "GET /api/profile": hasProfile,
  });
  renderApp("/login");

  await screen.findByText(/logged in as demo@example\.com/i);
});

function loggedOutThenIn() {
  let loggedIn = false;
  return {
    "GET /api/auth/me": () =>
      loggedIn
        ? { status: 200, body: { email: "demo@example.com" } }
        : { status: 401, body: { detail: "Not logged in." } },
    "GET /api/profile": hasProfile,
    "POST /api/auth/login": () => {
      loggedIn = true;
      return { status: 200, body: { email: "demo@example.com" } };
    },
  };
}

test("after login the user goes to the page they wanted, not just home", async () => {
  mockFetch(loggedOutThenIn());
  renderApp("/profile");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "demo-pass-123");

  await screen.findByRole("heading", { level: 1, name: /your profile/i });
});

test("a next link to another site is ignored", async () => {
  mockFetch(loggedOutThenIn());
  renderApp("/login?next=//evil.example");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "demo-pass-123");

  await screen.findByText(/logged in as demo@example\.com/i);
});

test("a next link back to the login page doesn't leave the user stuck", async () => {
  mockFetch(loggedOutThenIn());
  renderApp("/login?next=/login");

  await screen.findByRole("heading", { name: /log in/i });
  submitLogin("demo@example.com", "demo-pass-123");

  await screen.findByText(/logged in as demo@example\.com/i);
});

test("new visitors and wrong passwords never see 'session ended'", async () => {
  mockFetch({
    ...LOGGED_OUT,
    "POST /api/auth/login": () => ({
      status: 401,
      body: { detail: "Invalid email or password." },
    }),
  });
  renderApp("/login");

  await screen.findByRole("heading", { name: /log in/i });
  expect(screen.queryByText(/session has ended/i)).toBeNull();
  submitLogin("demo@example.com", "wrong-pass-1");
  await screen.findByRole("alert");

  expect(screen.queryByText(/session has ended/i)).toBeNull();
});
