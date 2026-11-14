import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";
import { screenIsWide } from "../test/screen";

// The shared app frame (feature 001, User Story 6, task T050; FR-027 as amended with 006, task
// T035): flat links on computers, a bar of four groups on phones.

const ME = { status: 200, body: { email: "demo@example.com" } };
const LOGGED_OUT = {
  "GET /api/auth/me": () => ({
    status: 401,
    body: { detail: "Not logged in." },
  }),
};
const LOGGED_IN = {
  "GET /api/auth/me": () => ME,
  "GET /api/profile": hasProfile,
  "GET /api/documents": () => ({ status: 200, body: [] }),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

const mainNav = () => screen.findByRole("navigation", { name: /main/i });

// Computers (720 px and wider).

test("the header has the app name home and the tax year", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  const banner = await screen.findByRole("banner");
  expect(
    within(banner)
      .getByRole("link", { name: /paktaxfiler/i })
      .getAttribute("href"),
  ).toBe("/");
  // "Tax year" is hidden on phones but still read out, so it is its own element.
  within(banner).getByText(
    (_, element) =>
      element?.tagName === "P" && element.textContent === "Tax year 2025-26",
  );
});

test("on a computer, the menu links every main page and marks the current one", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  const nav = await mainNav();
  const links = within(nav).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual([
    "Home",
    "Documents",
    "Tax",
    "Calculator",
    "Wealth statement",
    "Guided filing",
    "Ask",
  ]);
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/",
    "/documents",
    "/tax",
    "/calculator",
    "/wealth",
    "/workflow",
    "/ask",
  ]);
  expect(within(nav).getByRole("link", { current: "page" }).textContent).toBe(
    "Documents",
  );
  expect(screen.getAllByRole("navigation", { name: /main/i })).toHaveLength(1);
});

test("on a computer, the account menu holds Profile and Log out, and Escape closes it", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  const account = await screen.findByRole("button", { name: "Account" });
  expect(account.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("button", { name: /log out/i })).toBeNull();

  fireEvent.click(account);
  expect(account.getAttribute("aria-expanded")).toBe("true");
  const panel = document.getElementById(
    account.getAttribute("aria-controls")!,
  )!;
  expect(
    within(panel).getByRole("link", { name: "Profile" }).getAttribute("href"),
  ).toBe("/profile");
  within(panel).getByRole("button", { name: /log out/i });

  fireEvent.keyDown(document, { key: "Escape" });
  expect(account.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(account);
});

test("the account menu is marked as current on the profile page", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/profile");

  await screen.findByRole("heading", { name: /your profile/i });
  expect(
    screen
      .getByRole("button", { name: "Account" })
      .getAttribute("aria-current"),
  ).toBe("true");
});

test("'Skip to content' is the first link and points at the page content", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  await mainNav();
  const first = screen.getAllByRole("link")[0];
  expect(first.textContent).toBe("Skip to content");
  const target = first.getAttribute("href")?.slice(1) ?? "";
  expect(document.getElementById(target)).not.toBeNull();
});

test.each(["/login", "/signup", "/no-such-page"])(
  "%s has no navigation",
  async (path) => {
    mockFetch(LOGGED_OUT);
    renderApp(path);

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("navigation", { name: /main/i })).toBeNull();
  },
);

test("first-time profile setup has no navigation, but Log out is right there", async () => {
  mockFetch({ "GET /api/auth/me": () => ME, "GET /api/profile": noProfile });
  renderApp("/profile");

  await screen.findByRole("heading", { name: /set up your profile/i });
  expect(screen.queryByRole("navigation", { name: /main/i })).toBeNull();
  expect(screen.getAllByRole("button", { name: /log out/i })).toHaveLength(1);
});

test("pages no longer carry their own Home link", async () => {
  mockFetch({
    ...LOGGED_IN,
    "GET /api/tax/2025-26": () => new Promise(() => {}),
  });
  renderApp("/tax");

  await screen.findByRole("heading", { name: /your tax for 2025-26/i });
  const main = screen.getByRole("main");
  expect(within(main).queryByRole("link", { name: "Home" })).toBeNull();
});

// Phones (narrower than 720 px).

test("on a phone, the bar holds Home, Filing, Ask and Account", async () => {
  screenIsWide(false);
  mockFetch(LOGGED_IN);
  renderApp("/");

  const nav = await mainNav();
  const items = within(nav).getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "Home",
    "Filing",
    "Ask",
    "Account",
  ]);
  expect(within(nav).getByRole("link", { current: "page" }).textContent).toBe(
    "Home",
  );
  within(nav).getByRole("button", { name: "Filing" });
  within(nav).getByRole("button", { name: "Account" });
});

test("on a phone, Filing opens a sheet with its pages; a second tap or Escape closes it", async () => {
  screenIsWide(false);
  mockFetch(LOGGED_IN);
  renderApp("/");

  const filing = await screen.findByRole("button", { name: "Filing" });
  fireEvent.click(filing);
  expect(filing.getAttribute("aria-expanded")).toBe("true");
  const sheet = document.getElementById(filing.getAttribute("aria-controls")!)!;
  expect(
    within(sheet)
      .getAllByRole("link")
      .map((link) => [link.textContent, link.getAttribute("href")]),
  ).toEqual([
    ["Documents", "/documents"],
    ["Tax", "/tax"],
    ["Calculator", "/calculator"],
    ["Wealth statement", "/wealth"],
    ["Guided filing", "/workflow"],
  ]);

  fireEvent.click(filing);
  expect(filing.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(filing);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(filing.getAttribute("aria-expanded")).toBe("false");
  expect(document.activeElement).toBe(filing);
});

test("on a phone, choosing a page from a sheet goes there and closes the sheet", async () => {
  screenIsWide(false);
  mockFetch({
    ...LOGGED_IN,
    "GET /api/tax/2025-26": () => new Promise(() => {}),
  });
  renderApp("/");

  const filing = await screen.findByRole("button", { name: "Filing" });
  fireEvent.click(filing);
  fireEvent.click(screen.getByRole("link", { name: "Tax" }));

  await screen.findByRole("heading", { name: /your tax for 2025-26/i });
  expect(filing.getAttribute("aria-expanded")).toBe("false");
  // The group of the current page is marked.
  expect(filing.getAttribute("aria-current")).toBe("true");
});

test("on a phone, Account opens a sheet with Profile and Log out", async () => {
  screenIsWide(false);
  mockFetch(LOGGED_IN);
  renderApp("/");

  const account = await screen.findByRole("button", { name: "Account" });
  fireEvent.click(account);
  const sheet = document.getElementById(
    account.getAttribute("aria-controls")!,
  )!;
  within(sheet).getByRole("link", { name: "Profile" });
  within(sheet).getByRole("button", { name: /log out/i });
});
