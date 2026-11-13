import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Wealth } from "../api/wealth";
import { hasProfile, mockFetch, noDocuments } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { catchDownloads } from "../test/downloads";
import { renderApp } from "../test/renderApp";

// The wealth statement page, per specs/005-wealth-statement/contracts/wealth-api.md (tasks
// T011, T017, T023). Figures and results come from the backend; the page does no maths.

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
const SALARY_CERT = "Salary certificate uploaded 2026-11-09 14:05:02 UTC";

const SAVED: Wealth = {
  tax_year: "2025-26",
  statement: {
    previous_net_assets: "2100000",
    assets: [
      {
        category: "bank_account",
        description: "Savings account",
        amount: "1350000",
      },
    ],
    liabilities: [
      { description: "Car loan", creditor: "Bank", amount: "200000" },
    ],
    other_exempt_income: "0",
    foreign_remittance: "0",
    inheritance: "0",
    gifts_received: "0",
    family_contribution: "0",
    gifts_given: "0",
    expenses: { rent: "600000" },
    saved_at: "2026-11-10T10:00:00Z",
  },
  auto_filled: [
    {
      line: "7031",
      label: "Taxable salary",
      amount: "1800000",
      certificates: [SALARY_CERT],
      provisional: false,
    },
    {
      line: null,
      label: "Tax deducted and withheld at source (outflow)",
      amount: "82000",
      certificates: [SALARY_CERT],
      provisional: true,
    },
  ],
  certificates_changed: false,
  result: {
    not_ready_reason: null,
    message: "Your wealth statement reconciles.",
    net_assets: "1150000",
    increase: "-950000",
    inflows: "1800000",
    outflows: "2750000",
    unreconciled: "0",
    direction: "reconciled",
    where_to_look: [],
    steps: [
      {
        description:
          "Net assets this year: Rs 1,350,000 - Rs 200,000 = Rs 1,150,000",
        form_line: "703001",
        result: "1150000",
      },
      {
        description:
          "Unreconciled amount: Rs 1,800,000 - Rs 2,750,000 - (-Rs 950,000) = Rs 0",
        form_line: "703000",
        result: "0",
      },
    ],
  },
  label: LABEL,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The summary request's answer: a summary, none (dropped), or one that never arrives. */
type Summary = string | null | "pending";

function serve(
  wealth: Partial<Wealth> = {},
  onSave?: (body: unknown) => FakeReply | Promise<FakeReply>,
  summary: Summary = null,
) {
  const reply = (): FakeReply => ({
    status: 200,
    body: { ...SAVED, ...wealth },
  });
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/documents": noDocuments,
    "GET /api/profile": hasProfile,
    "GET /api/wealth/2025-26": reply,
    "GET /api/wealth/2025-26/pdf": () => ({ status: 200, body: {} }),
    "PUT /api/wealth/2025-26": ({ body }) => (onSave ? onSave(body) : reply()),
    "GET /api/wealth/2025-26/summary": () =>
      summary === "pending"
        ? new Promise<FakeReply>(() => {})
        : { status: 200, body: { summary } },
  });
}

async function open() {
  renderApp("/wealth");
  await screen.findByRole("heading", { name: /wealth statement for 2025-26/i });
  await screen.findByText(LABEL); // the statement has loaded
}

test("opens on the profile's tax year with three sections and the label", async () => {
  serve();
  await open();

  screen.getByRole("region", { name: /what i own/i });
  screen.getByRole("region", { name: /what i owe/i });
  screen.getByRole("region", { name: /money in and out/i });
  screen.getByText(LABEL);
});

test("the saved rows and amounts are filled in", async () => {
  serve();
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  expect(within(own).getByLabelText(/description/i)).toHaveProperty(
    "value",
    "Savings account",
  );
  expect(within(own).getByLabelText(/amount/i)).toHaveProperty(
    "value",
    "1350000",
  );
  expect(screen.getByLabelText(/net assets on 30 june 2025/i)).toHaveProperty(
    "value",
    "2100000",
  );
  expect(screen.getByRole("textbox", { name: /^rent$/i })).toHaveProperty(
    "value",
    "600000",
  );
});

test("adding, editing and removing rows is what gets saved", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  fireEvent.click(within(own).getByRole("button", { name: /add an asset/i }));
  const second = within(own).getByRole("group", { name: "Asset 2" });
  expect(within(second).getByLabelText(/category/i)).toHaveProperty(
    "value",
    "bank_account",
  );
  fireEvent.change(within(second).getByLabelText(/category/i), {
    target: { value: "motor_vehicle" },
  });
  fireEvent.change(within(second).getByLabelText(/description/i), {
    target: { value: "Car" },
  });
  fireEvent.change(within(second).getByLabelText(/amount/i), {
    target: { value: "1400000" },
  });
  const owe = screen.getByRole("region", { name: /what i owe/i });
  fireEvent.click(
    within(owe).getByRole("button", { name: "Remove liability 1" }),
  );
  expect(document.activeElement).toBe(
    within(owe).getByRole("button", { name: /add a liability/i }),
  );
  fireEvent.click(
    within(owe).getByRole("button", { name: /add a liability/i }),
  );
  const loan = within(owe).getByRole("group", { name: "Liability 1" });
  fireEvent.change(within(loan).getByLabelText(/description/i), {
    target: { value: "Loan from a friend" },
  });
  fireEvent.change(within(loan).getByLabelText(/amount/i), {
    target: { value: "5000" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.assets).toEqual([
    {
      category: "bank_account",
      description: "Savings account",
      amount: "1350000",
    },
    { category: "motor_vehicle", description: "Car", amount: "1400000" },
  ]);
  expect(saved?.liabilities).toEqual([
    { description: "Loan from a friend", creditor: null, amount: "5000" },
  ]);
  expect(saved?.previous_net_assets).toBe("2100000");
});

test("removing an asset removes it from what is saved", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  fireEvent.click(within(own).getByRole("button", { name: "Remove asset 1" }));
  expect(document.activeElement).toBe(
    within(own).getByRole("button", { name: /add an asset/i }),
  );
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.assets).toEqual([]);
});

test("descriptions are required and sent trimmed", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const asset = screen.getByRole("group", { name: "Asset 1" });
  const description = within(asset).getByLabelText(/description/i);
  expect(description).toHaveProperty("required", true);
  const liability = screen.getByRole("group", { name: "Liability 1" });
  expect(within(liability).getByLabelText(/description/i)).toHaveProperty(
    "required",
    true,
  );
  fireEvent.change(description, { target: { value: "  Savings account  " } });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  const assets = (saved?.assets ?? []) as { description: string }[];
  expect(assets[0].description).toBe("Savings account");
});

test("empty fields are sent as not entered, zero or left out, and amounts trimmed", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  fireEvent.change(screen.getByLabelText(/net assets on 30 june 2025/i), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByLabelText(/inheritance/i), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: /^rent$/i }), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByRole("textbox", { name: /^medical$/i }), {
    target: { value: " 5000 " },
  });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.previous_net_assets).toBeNull();
  expect(saved?.inheritance).toBe("0");
  expect(saved?.expenses).toEqual({ medical: "5000" });
});

test("last year's net assets can be negative, so its keypad isn't digits-only", async () => {
  serve();
  await open();

  const previous = screen.getByLabelText(/net assets on 30 june 2025/i);
  expect(previous.getAttribute("inputmode")).toBeNull();
  const hint = document.getElementById(
    previous.getAttribute("aria-describedby") ?? "",
  );
  expect(hint?.textContent).toMatch(/may be negative/i);
  screen.getByText(/as on 30 june 2026/i);
});

test("the dates follow the profile's tax year", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/documents": noDocuments,
    "GET /api/profile": () => ({
      status: 200,
      body: {
        profile: {
          tax_year: "2024-25",
          on_atl: true,
          updated_at: "2026-11-05T10:00:00Z",
        },
        supported_tax_years: ["2024-25"],
      },
    }),
    "GET /api/wealth/2024-25": () => ({
      status: 200,
      body: { ...SAVED, tax_year: "2024-25" },
    }),
  });
  renderApp("/wealth");
  await screen.findByText(LABEL);

  screen.getByLabelText(/net assets on 30 june 2024/i);
  screen.getByText(/as on 30 june 2025/i);
});

test("certificate lines are read-only, name their certificate and say how to correct it", async () => {
  serve({
    auto_filled: [
      ...SAVED.auto_filled,
      {
        line: "7033",
        label: "Bank profit",
        amount: "0",
        certificates: [],
        provisional: true,
      },
    ],
  });
  await open();

  const money = screen.getByRole("region", { name: /money in and out/i });
  const fromCertificates = within(money).getByRole("list", {
    name: /from your certificates/i,
  });
  within(fromCertificates).getByText(/taxable salary \(7031\)/i);
  within(fromCertificates).getByText("Rs 1,800,000");
  expect(
    within(fromCertificates).getAllByText(new RegExp(SALARY_CERT)).length,
  ).toBeGreaterThan(0);
  within(fromCertificates).getByText("No confirmed certificate");
  expect(screen.queryByLabelText(/taxable salary/i)).toBeNull(); // nothing to type into
  within(money).getByText(/correct the certificate/i);
});

test("a save replaces the form and result with what the server saved, and says so", async () => {
  serve({}, () => ({
    status: 200,
    body: {
      ...SAVED,
      statement: {
        ...SAVED.statement,
        assets: [
          { category: "bank_account", description: "Renamed", amount: "1" },
        ],
      },
      result: { ...SAVED.result, message: "Saved and recalculated." },
    },
  }));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await screen.findByText("Saved and recalculated.");
  const own = screen.getByRole("region", { name: /what i own/i });
  expect(within(own).getByLabelText(/description/i)).toHaveProperty(
    "value",
    "Renamed",
  );
  screen.getByText("Saved.");
  // Keyboard and screen-reader users stay where they were, not at the top of the page. Focus
  // moves just after the page updates, so wait for it.
  await waitFor(() =>
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: /^save$/i }),
    ),
  );
});

test("there is one status region, so the save is announced, and the certificate notice isn't one", async () => {
  serve({ certificates_changed: true });
  await open();

  const statuses = screen.getAllByRole("status");
  expect(statuses).toHaveLength(1);
  expect(statuses[0].textContent).toBe("");
  expect(
    screen
      .getByText(/your confirmed certificates changed since you last saved/i)
      .getAttribute("role"),
  ).toBeNull();
});

test("while saving, nothing can be typed or saved twice", async () => {
  serve({}, () => new Promise<FakeReply>(() => {}));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  const saving = await screen.findByRole("button", { name: /saving/i });
  expect(saving).toHaveProperty("disabled", true);
  expect(
    screen.getByLabelText(/inheritance/i).closest("fieldset"),
  ).toHaveProperty("disabled", true);
});

test("a save error is shown beside the save button", async () => {
  serve({}, () => ({
    status: 422,
    body: { detail: "inheritance: must not be negative" },
  }));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("must not be negative");
  const save = screen.getByRole("button", { name: /^save$/i });
  expect(save.getAttribute("aria-describedby")).toBe(alert.id);
  await waitFor(() => expect(document.activeElement).toBe(save));
});

test("a statement that can't be loaded says so", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/documents": noDocuments,
    "GET /api/profile": hasProfile,
    "GET /api/wealth/2025-26": () => ({
      status: 500,
      body: { detail: "Server error." },
    }),
  });
  renderApp("/wealth");

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /server error/i,
  );
});

// Task T017 (User Story 2): the result explained.

test("the breakdown shows each step with its form line", async () => {
  serve();
  await open();

  const breakdown = screen.getByRole("list", {
    name: /how it was worked out/i,
  });
  const steps = within(breakdown).getAllByRole("listitem");
  expect(steps).toHaveLength(2);
  within(steps[0]).getByText(/Net assets this year/);
  within(steps[0]).getByText(/703001/);
  screen.getByText("Your wealth statement reconciles.");
  expect(screen.queryByRole("list", { name: /where to look/i })).toBeNull();
  // No summary (the request answers none): the panel goes once that answer arrives.
  await waitFor(() =>
    expect(screen.queryByRole("region", { name: /summary/i })).toBeNull(),
  );
  within(screen.getByRole("region", { name: /^result$/i })).getByText(LABEL);
});

test("a gap shows its message, where to look, and the summary when there is one", async () => {
  serve(
    {
      result: {
        ...SAVED.result,
        unreconciled: "-50000",
        direction: "growth_exceeds_inflows",
        message:
          "Your assets grew Rs 50,000 more than your inflows explain: an inflow may be missing.",
        where_to_look: ["A gift you received", "An inheritance"],
      },
    },
    undefined,
    "Your assets grew Rs 50,000 more than your inflows explain.",
  );
  await open();

  screen.getByText(
    /assets grew Rs 50,000 more than your inflows explain: an inflow/,
  );
  const look = screen.getByRole("list", { name: /where to look/i });
  within(look).getByText("A gift you received");
  await within(
    await screen.findByRole("region", { name: /summary/i }),
  ).findByText("Your assets grew Rs 50,000 more than your inflows explain.");
});

// Feature 001, User Story 6: the statement never waits for the AI summary.

test("the statement shows while its summary is still being written, and asks again after a save", async () => {
  const fake = serve({}, undefined, "pending");
  await open();

  within(screen.getByRole("region", { name: /summary/i })).getByText(
    "Writing a short summary…",
  );
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
  await screen.findByText("Saved.");
  await waitFor(() =>
    expect(
      fake.mock.calls.filter(([url]) => String(url).endsWith("/summary")),
    ).toHaveLength(2),
  );
});

// Task T023 (User Story 3): honest limits and staying in sync.

test("a not-ready statement shows what to do and no breakdown", async () => {
  serve({
    result: {
      ...SAVED.result,
      not_ready_reason: "needs_previous_net_assets",
      message:
        "Enter your net assets as on 30 June 2025, from last year's wealth statement.",
      net_assets: null,
      increase: null,
      inflows: null,
      outflows: null,
      unreconciled: null,
      direction: null,
      steps: [],
    },
  });
  await open();

  screen.getByText(/enter your net assets as on 30 june 2025, from last year/i);
  expect(
    screen.queryByRole("list", { name: /how it was worked out/i }),
  ).toBeNull();
  expect(screen.queryByRole("list", { name: /where to look/i })).toBeNull();
  expect(screen.queryByRole("region", { name: /summary/i })).toBeNull();
  screen.getByText(LABEL);
});

test("changed certificates since the last save are pointed out", async () => {
  serve({ certificates_changed: true });
  await open();

  screen.getByText(/your confirmed certificates changed since you last saved/i);
});

test("the home page links to the wealth statement", async () => {
  serve();
  renderApp("/");

  // From its checklist (feature 001, User Story 6) as well as the navigation.
  const link = await screen.findByRole("link", {
    name: "Open wealth statement",
  });
  expect(link.getAttribute("href")).toBe("/wealth");
});

// Feature 001, User Story 6, task T055: a section bar to jump between the parts on a phone, and
// the result's answer before its detail.

test("a section bar links to each part of the statement", async () => {
  serve();
  await open();

  const bar = screen.getByRole("navigation", { name: /sections/i });
  const links = within(bar).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual([
    "What I own",
    "What I owe",
    "Money in and out",
    "Result",
  ]);
  for (const link of links) {
    const target = document.getElementById(link.getAttribute("href")!.slice(1));
    expect(target?.textContent).toBe(link.textContent);
  }
});

test("the result shows its label, then its message, then where to look", async () => {
  serve({
    result: {
      ...SAVED.result,
      unreconciled: "-50000",
      direction: "growth_exceeds_inflows",
      message:
        "Your assets grew Rs 50,000 more than your inflows explain: an inflow may be missing.",
      where_to_look: ["A gift you received"],
    },
  });
  await open();

  const result = screen.getByRole("region", { name: /^result$/i });
  const label = within(result).getByText(LABEL);
  const message = within(result).getByText(/assets grew Rs 50,000/);
  const look = within(result).getByRole("list", { name: /where to look/i });
  const follows = (a: Node, b: Node) =>
    Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  expect(follows(label, message)).toBe(true);
  expect(follows(message, look)).toBe(true);
});

test("while the statement loads, 'Loading…' is announced (task T062)", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/wealth/2025-26": () => new Promise(() => {}),
  });
  renderApp("/wealth");

  // The page's own heading first: the profile's loading message is also a status.
  await screen.findByRole("heading", { name: /wealth statement for 2025-26/i });
  expect(screen.getByRole("status").textContent).toBe("Loading…");
});

// Feature 001, User Story 6, tasks T066 and T068.

test("an amount typed in is repeated with digit grouping, and nothing for a non-number", async () => {
  serve();
  await open();

  const field = screen.getByRole("textbox", { name: /^inheritance$/i });
  fireEvent.change(field, { target: { value: "1500000" } });
  screen.getByText("Rs 1,500,000");
  fireEvent.change(field, { target: { value: "15 lakh" } });
  expect(screen.queryByText(/Rs 15/)).toBeNull();
});

test("the personal expenses can be folded away and say how many are filled", async () => {
  serve();
  await open();

  const summary = screen.getByText(/personal expenses/i, {
    selector: "summary",
  });
  const panel = summary.parentElement as HTMLDetailsElement;
  expect(panel.open).toBe(true);
  expect(summary.textContent).toBe("Personal expenses (1 of 16 filled)");
  fireEvent.change(screen.getByRole("textbox", { name: /^water$/i }), {
    target: { value: "500" },
  });
  expect(summary.textContent).toBe("Personal expenses (2 of 16 filled)");
});

// ---- PDF export (feature 008, task T008) ----

test("a reconciled statement downloads its PDF", async () => {
  const fetch = serve();
  const saved = catchDownloads();
  await open();

  const button = screen.getByRole("button", { name: "Download PDF" });
  expect(button.getAttribute("aria-disabled")).toBe("false");
  fireEvent.click(button);

  await waitFor(() => expect(saved).toHaveLength(1));
  expect(fetch).toHaveBeenCalledWith(
    "/api/wealth/2025-26/pdf",
    expect.anything(),
  );
});

test("unsaved changes must be saved before the PDF, which is of the saved statement", async () => {
  serve();
  await open();

  fireEvent.change(screen.getByLabelText(/net assets on 30 june 2025/i), {
    target: { value: "2200000" },
  });

  const button = screen.getByRole("button", {
    name: "Download PDF",
    description: "Save your changes first: the PDF is of your saved statement.",
  });
  expect(button.getAttribute("aria-disabled")).toBe("true");
});

test("a statement not ready yet says why there is no PDF", async () => {
  serve({
    result: {
      ...SAVED.result,
      not_ready_reason: "needs_previous_net_assets",
      message: "Enter last year's net assets to reconcile.",
    },
  });
  await open();

  const button = await screen.findByRole("button", {
    name: "Download PDF",
    description: "No PDF until your statement can be reconciled.",
  });
  expect(button.getAttribute("aria-disabled")).toBe("true");
});
