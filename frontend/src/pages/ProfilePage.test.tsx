import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import {
  hasProfile,
  mockFetch,
  noProfile,
  SAVED_PROFILE,
} from "../test/mockFetch";
import type { FakeRoutes } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Taxpayer profile setup, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T037,
// FR-016, FR-019, FR-020).

const FBR_ATL_PAGE =
  "https://www.fbr.gov.pk/categ/active-taxpayer-list-income-tax/51147/30859/71169";
const ME = { status: 200, body: { email: "demo@example.com" } };

afterEach(() => {
  vi.unstubAllGlobals();
});

/** A logged-in user without a profile; PUT saves it and later reads return it. */
function newUser(): { routes: FakeRoutes; saved: () => unknown } {
  let saved: unknown = null;
  return {
    saved: () => saved,
    routes: {
      "GET /api/auth/me": () => ME,
      "GET /api/profile": () =>
        saved
          ? {
              status: 200,
              body: { profile: saved, supported_tax_years: ["2025-26"] },
            }
          : noProfile(),
      "PUT /api/profile": ({ body }) => {
        saved = { ...SAVED_PROFILE, ...(body as object) };
        return { status: 200, body: saved };
      },
    },
  };
}

test("a user without a profile opening the home page is sent to the setup step", async () => {
  mockFetch(newUser().routes);
  renderApp("/");

  await screen.findByRole("heading", {
    level: 1,
    name: /set up your profile/i,
  });
});

test("the setup step offers only the supported tax years and no preselected ATL answer", async () => {
  mockFetch(newUser().routes);
  renderApp("/profile");

  const taxYear = await screen.findByLabelText(/tax year/i);
  const options = within(taxYear)
    .getAllByRole("option")
    .map((o) => o.textContent);
  expect(options).toEqual(["2025-26"]);
  expect(screen.getByRole("radio", { name: /yes/i })).toHaveProperty(
    "checked",
    false,
  );
  expect(screen.getByRole("radio", { name: /no/i })).toHaveProperty(
    "checked",
    false,
  );
});

test("shows FBR's ATL check link, the residency notice and the logout button", async () => {
  mockFetch(newUser().routes);
  renderApp("/profile");

  const link = await screen.findByRole("link", {
    name: /check your atl status on fbr's website/i,
  });
  expect(link.getAttribute("href")).toBe(FBR_ATL_PAGE);
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toContain("noopener");
  screen.getByText(
    /this app covers people who live in pakistan and earn a salary\./i,
  );
  screen.getByRole("button", { name: /log out/i });
});

test("saving without an ATL answer is refused with a message", async () => {
  const user = newUser();
  const fake = mockFetch(user.routes);
  renderApp("/profile");

  fireEvent.click(await screen.findByRole("button", { name: /save/i }));

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Tell us whether you are on the ATL.",
  );
  const puts = fake.mock.calls.filter(([, init]) => init?.method === "PUT");
  expect(puts).toHaveLength(0);
});

test("saving the answers goes on to the page the user wanted", async () => {
  const user = newUser();
  mockFetch(user.routes);
  renderApp("/profile?next=/");

  fireEvent.click(await screen.findByRole("radio", { name: /no/i }));
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  await screen.findByText(/logged in as demo@example\.com/i);
  expect(user.saved()).toMatchObject({ tax_year: "2025-26", on_atl: false });
});

test("the home page links to the profile, which shows the saved answers for editing", async () => {
  const user = newUser();
  mockFetch(user.routes);
  renderApp("/profile?next=/");
  fireEvent.click(await screen.findByRole("radio", { name: /yes/i }));
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  fireEvent.click(await screen.findByRole("link", { name: /profile/i }));

  await screen.findByRole("heading", { level: 1, name: /your profile/i });
  expect(screen.getByRole("radio", { name: /yes/i })).toHaveProperty(
    "checked",
    true,
  );
});

test("changing ATL status saves the new answer", async () => {
  const user = newUser();
  mockFetch(user.routes);
  renderApp("/profile?next=/");
  fireEvent.click(await screen.findByRole("radio", { name: /yes/i }));
  fireEvent.click(screen.getByRole("button", { name: /save/i }));
  fireEvent.click(await screen.findByRole("link", { name: /profile/i }));

  fireEvent.click(await screen.findByRole("radio", { name: /no/i }));
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  await screen.findByText(/logged in as demo@example\.com/i);
  expect(user.saved()).toMatchObject({ on_atl: false });
});

test("if the profile can't be loaded, the user is told and can retry", async () => {
  let failing = true;
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": () =>
      failing
        ? { status: 500, body: { detail: "Server error." } }
        : noProfile(),
  });
  renderApp("/");

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    expect.stringMatching(/couldn't load your profile/i),
  );
  failing = false;
  fireEvent.click(screen.getByRole("button", { name: /try again/i }));

  await screen.findByRole("heading", {
    level: 1,
    name: /set up your profile/i,
  });
});

test("after one user logs out, the next user doesn't see the first user's profile", async () => {
  let current: string | null = "a@example.com";
  mockFetch({
    "GET /api/auth/me": () =>
      current
        ? { status: 200, body: { email: current } }
        : { status: 401, body: { detail: "Not logged in." } },
    "GET /api/profile": () =>
      current === "a@example.com" ? hasProfile() : noProfile(),
    "POST /api/auth/logout": () => {
      current = null;
      return { status: 204 };
    },
    "POST /api/auth/login": () => {
      current = "b@example.com";
      return { status: 200, body: { email: current } };
    },
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));
  await screen.findByRole("heading", { name: /log in/i });
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: "b@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: "b-pass-123" },
  });
  fireEvent.click(screen.getByRole("button", { name: /log in/i }));

  await screen.findByRole("heading", {
    level: 1,
    name: /set up your profile/i,
  });
});
