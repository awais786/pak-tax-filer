import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { TaxResult } from "../api/tax";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { catchDownloads } from "../test/downloads";
import { renderApp } from "../test/renderApp";

// The tax result page, per specs/004-tax-engine/contracts/tax-api.md (tasks T013, T019, T023).
// Figures are shown as the API gives them; the page does no tax maths (Principle I).

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";

const CALCULATED: TaxResult = {
  tax_year: "2025-26",
  blocked_reason: null,
  message: null,
  salary_tax: "72000",
  surcharge: "0",
  profit_tax: "20000",
  salary_balance: "12000",
  profit_balance: "-4000",
  non_atl_extra_withheld: null,
  salary_credit: "60000",
  profit_credit: "24000",
  steps: [
    {
      description:
        "Salary tax: Rs 6,000 + 11% of Rs 600,000 above Rs 1,200,000 = Rs 72,000",
      rule_location: "First Schedule, Part I, Division I, clause (2), row 3",
      result: "72000",
    },
    {
      description:
        "Tax on bank profit: 20% of gross profit Rs 100,000 = Rs 20,000",
      rule_location: "First Schedule, Part I, Division IIIA",
      result: "20000",
    },
  ],
  label: LABEL,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The summary request's answer: a summary, none (dropped), or one that never arrives. */
type Summary = string | null | "pending";

function showTax(result: Partial<TaxResult>, summary: Summary = null) {
  const reply = (): FakeReply => ({
    status: 200,
    body: { ...CALCULATED, ...result },
  });
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/tax/2025-26": reply,
    "GET /api/tax/2025-26/pdf": () => ({ status: 200, body: {} }),
    "GET /api/tax/2025-26/summary": () =>
      summary === "pending"
        ? new Promise<FakeReply>(() => {})
        : { status: 200, body: { summary } },
  });
}

function blocked(reason: string, message: string): Partial<TaxResult> {
  return {
    blocked_reason: reason,
    message,
    salary_tax: null,
    surcharge: null,
    profit_tax: null,
    salary_balance: null,
    profit_balance: null,
    steps: [],
  };
}

test("asks for the profile's tax year and never asks for ATL status itself", async () => {
  const fetch = showTax({});
  renderApp("/tax");

  await screen.findByRole("heading", { name: /your tax for 2025-26/i });
  // The heading shows before the page asks for its tax, so wait for the request.
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith("/api/tax/2025-26", expect.anything()),
  );
  expect(screen.queryByText(/active taxpayer/i)).toBeNull();
  expect(screen.queryByRole("radio")).toBeNull();
});

test("salary and bank profit results are shown separately, with no combined total", async () => {
  showTax({});
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  within(salary).getByText("Rs 72,000");
  within(salary).getByText("Rs 12,000 payable");
  const profit = screen.getByRole("region", { name: /bank profit/i });
  within(profit).getByText("Rs 20,000");
  within(profit).getByText("Rs 4,000 over-withheld");
  expect(screen.queryByText(/total/i)).toBeNull();
});

test("the practitioner label is always shown", async () => {
  showTax({});
  renderApp("/tax");

  await screen.findByText(LABEL);
});

test("the breakdown shows every step with its rule location", async () => {
  showTax({});
  renderApp("/tax");

  const breakdown = await screen.findByRole("list", {
    name: /how it was worked out/i,
  });
  const steps = within(breakdown).getAllByRole("listitem");
  expect(steps).toHaveLength(2);
  within(steps[0]).getByText(/Rs 6,000 \+ 11% of Rs 600,000/);
  within(steps[0]).getByText(/clause \(2\), row 3/);
  within(steps[1]).getByText(/Division IIIA/);
});

test("the summary is shown only when the API sends one", async () => {
  showTax({}, "Your salary tax is Rs 72,000; Rs 12,000 is payable.");
  const first = renderApp("/tax");
  await screen.findByText(
    /Your salary tax is Rs 72,000; Rs 12,000 is payable\./,
  );
  first.unmount();
  vi.unstubAllGlobals();

  showTax({}, null);
  renderApp("/tax");
  await screen.findByRole("list", { name: /how it was worked out/i });
  await waitFor(() =>
    expect(screen.queryByText(/writing a short summary/i)).toBeNull(),
  );
  expect(screen.queryByRole("region", { name: /summary/i })).toBeNull();
});

// Feature 001, User Story 6: the figures never wait for the AI summary, which has its own request.

test("the figures show while the summary is still being written", async () => {
  showTax({}, "pending");
  renderApp("/tax");

  await screen.findByRole("region", { name: /salary/i });
  const panel = screen.getByRole("region", { name: /summary/i });
  within(panel).getByText("Writing a short summary…");
});

test("a refused calculation never asks for a summary", async () => {
  const fake = showTax(
    blocked("needs_atl_answer", "Set your ATL status in your profile."),
    "Rs 1",
  );
  renderApp("/tax");

  await screen.findByText("Set your ATL status in your profile.");
  const asked = fake.mock.calls.some(([url]) =>
    String(url).endsWith("/summary"),
  );
  expect(asked).toBe(false);
});

test("without ATL status it links to the profile, with no figures", async () => {
  showTax(blocked("needs_atl_answer", "Set your ATL status in your profile."));
  renderApp("/tax");

  await screen.findByText("Set your ATL status in your profile.");
  expect(
    screen
      .getByRole("link", { name: /go to your profile/i })
      .getAttribute("href"),
  ).toBe("/profile");
  expect(
    screen.queryByRole("list", { name: /how it was worked out/i }),
  ).toBeNull();
  screen.getByText(LABEL);
});

test("without a confirmed salary certificate it links to documents", async () => {
  showTax(
    blocked(
      "no_confirmed_salary_certificate",
      "Upload and confirm your salary certificate first.",
    ),
  );
  renderApp("/tax");

  await screen.findByText("Upload and confirm your salary certificate first.");
  expect(
    screen.getByRole("link", { name: /go to documents/i }).getAttribute("href"),
  ).toBe("/documents");
});

test.each([
  ["profit_over_limit", "Bank profit over Rs 5,000,000 isn't supported yet."],
  [
    "salary_share_ambiguous",
    "Your situation needs a tax practitioner: salary.",
  ],
  [
    "surcharge_ambiguous",
    "Your situation needs a tax practitioner: surcharge.",
  ],
])("a %s refusal shows the server's message", async (reason, message) => {
  showTax(blocked(reason, message));
  renderApp("/tax");

  await screen.findByText(message);
  expect(screen.queryByRole("region", { name: /salary/i })).toBeNull();
  screen.getByText(LABEL);
});

test("extra withholding for a non-ATL user is 'to be confirmed', never a refund", async () => {
  showTax({ profit_balance: "0", non_atl_extra_withheld: "40000" });
  renderApp("/tax");

  const profit = await screen.findByRole("region", { name: /bank profit/i });
  within(profit).getByText(
    "Rs 40,000 extra tax withheld; whether it can be reclaimed needs confirmation",
  );
  within(profit).getByText("Nothing to pay");
  expect(screen.queryByText(/refund/i)).toBeNull();
});

test("money with paisa keeps them", async () => {
  showTax({ salary_tax: "1234567.5" });
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  within(salary).getByText("Rs 1,234,567.5");
});

test("a negative salary balance reads over-deducted", async () => {
  showTax({ salary_balance: "-3000" });
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  within(salary).getByText("Rs 3,000 over-deducted");
});

test("a missing amount is left out, never shown as Rs 0", async () => {
  showTax({ surcharge: null });
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  expect(within(salary).queryByText("Surcharge")).toBeNull();
  within(salary).getByText("Rs 72,000");
});

test("an error reply is shown instead of the result", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/tax/2025-26": () => ({
      status: 404,
      body: { detail: "No rates for that tax year." },
    }),
  });
  renderApp("/tax");

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe("No rates for that tax year.");
});

// Feature 001, User Story 6, task T054: the answer first. Each side's balance is its headline,
// above the parts it is made of; the summary and the breakdown come after both sides.

const follows = (first: Node, second: Node) =>
  Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING,
  );

test("the label comes first, then each side's balance as its headline, then the detail", async () => {
  showTax({}, "Your tax is Rs 72,000.");
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  const profit = screen.getByRole("region", { name: /bank profit/i });
  await screen.findByText("Your tax is Rs 72,000.");
  expect(follows(screen.getByText(LABEL), salary)).toBe(true);
  expect(
    follows(
      within(salary).getByText("Rs 12,000 payable"),
      within(salary).getByText("Rs 72,000"),
    ),
  ).toBe(true);
  expect(
    follows(
      within(profit).getByText("Rs 4,000 over-withheld"),
      within(profit).getByText("Rs 20,000"),
    ),
  ).toBe(true);
  expect(
    follows(profit, screen.getByRole("region", { name: /summary/i })),
  ).toBe(true);
  expect(
    follows(
      profit,
      screen.getByRole("list", { name: /how it was worked out/i }),
    ),
  ).toBe(true);
  expect(screen.queryByText(/total/i)).toBeNull();
});

test("while the tax is worked out, 'Calculating…' is announced (task T062)", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/tax/2025-26": () => new Promise(() => {}),
  });
  renderApp("/tax");

  // The page's own heading first: the profile's loading message is also a status.
  await screen.findByRole("heading", { name: /your tax for 2025-26/i });
  expect(screen.getByRole("status").textContent).toBe("Calculating…");
});

// Feature 001, User Story 6: each side reads as a sum (tax, less what was already taken, then
// the balance), with the credits as the API gives them; the page adds nothing up itself.

test("each side shows what was already taken off, so it reads as a sum", async () => {
  showTax({});
  renderApp("/tax");

  const salary = await screen.findByRole("region", { name: /salary/i });
  within(salary).getByText("Less tax deducted by employers");
  within(salary).getByText("− Rs 60,000");
  const profit = screen.getByRole("region", { name: /bank profit/i });
  within(profit).getByText("Less tax withheld by banks");
  within(profit).getByText("− Rs 24,000");
  expect(screen.queryByText(/total/i)).toBeNull();
});

// ---- PDF export (feature 008, task T008) ----

test("a calculated result downloads its PDF", async () => {
  const fetch = showTax({});
  const saved = catchDownloads();
  renderApp("/tax");

  const button = await screen.findByRole("button", { name: "Download PDF" });
  expect(button.getAttribute("aria-disabled")).toBe("false");
  fireEvent.click(button);

  await waitFor(() => expect(saved).toHaveLength(1));
  expect(fetch).toHaveBeenCalledWith("/api/tax/2025-26/pdf", expect.anything());
});

test("a blocked result says why there is no PDF", async () => {
  showTax(blocked("needs_atl_answer", "Set your ATL status in your profile."));
  renderApp("/tax");

  const button = await screen.findByRole("button", {
    name: "Download PDF",
    description: "No PDF until this result can be calculated.",
  });
  expect(button.getAttribute("aria-disabled")).toBe("true");
});
