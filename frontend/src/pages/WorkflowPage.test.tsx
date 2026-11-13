import {
  act,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Run } from "../api/workflow";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The guided run, per specs/007-agentic-workflow/contracts/workflow-api.md (task T011). The
// page shows what the backend decided and checked; it computes nothing (Principle I).

const ME = { status: 200, body: { email: "demo@example.com" } };

const AT_GATE: Run = {
  step: "gate",
  tax_year: "2025-26",
  fingerprint: "f".repeat(64),
  document: {
    message: "Your salary certificate is confirmed.",
    missing: [],
    fallback: false,
  },
  validation: {
    message: "Your salary certificate shows taxable salary above gross salary.",
    issues: [
      {
        document_id: "doc-1",
        certificate: "Salary certificate uploaded 05 Nov 2026",
        field: "taxable_salary",
        reason: "Taxable salary is more than gross salary.",
      },
    ],
    fallback: false,
  },
  research: {
    note: "Your employer deducts tax from your salary.",
    passages: [
      {
        id: "p-1",
        source: "Income Tax Ordinance, 2001",
        kind: "law",
        location: "§149(1)",
        page: 327,
        text: "Every employer paying salary shall deduct tax.",
      },
    ],
    fallback: true,
  },
  gate: {
    figures: {
      taxable_salary: "1800000.00",
      tax_deducted: "75000.00",
      gross_profit: "0.00",
      tax_withheld: "0.00",
    },
    on_atl: true,
  },
  approved_at: null,
  done_at: null,
  inputs_changed: false,
};

const MISSING: Run = {
  ...AT_GATE,
  step: "document",
  document: {
    message: "You need a confirmed salary certificate.",
    missing: ["salary_certificate"],
    fallback: true,
  },
  validation: null,
  research: null,
  gate: null,
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** The app at /workflow: GET answers `current` (or 404), POST /start answers `started`. */
function showWorkflow(current: Run | null, started: Run | "pending" = AT_GATE) {
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () =>
      current === null
        ? { status: 404, body: { detail: "No guided run yet." } }
        : { status: 200, body: current },
    "POST /api/workflow/start": () =>
      started === "pending"
        ? new Promise<FakeReply>(() => {})
        : { status: 200, body: started },
  });
}

test("before a run, the page explains it and offers to start", async () => {
  const fetch = showWorkflow(null);
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  expect(await screen.findByText("Rs 1,800,000.00")).toBeDefined();
  expect(fetch).toHaveBeenCalledWith(
    "/api/workflow/start",
    expect.objectContaining({ method: "POST" }),
  );
});

test("while the steps run, it shows what each is doing in turn", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  showWorkflow(null, "pending");
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  const status = screen.getByRole("status");
  expect(status.textContent).toBe("Checking your documents…");
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(status.textContent).toBe("Checking the figures…");
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(status.textContent).toBe("Finding the law that applies…");
});

test("the step indicator marks where the run is and the steps already done", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  const steps = await screen.findByRole("list", { name: "Steps" });
  const current = within(steps).getByRole("listitem", { current: "step" });
  expect(current.textContent).toBe("Approve");
  const items = within(steps).getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "Documents (done)",
    "Figures (done)",
    "Law (done)",
    "Approve",
    "Result",
  ]);
});

test("a missing salary certificate is explained, with the way to fix it", async () => {
  showWorkflow(MISSING);
  renderApp("/workflow");

  expect(
    await screen.findByText("You need a confirmed salary certificate."),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Go to documents" }).getAttribute("href"),
  ).toBe("/documents");
  expect(
    screen.queryByRole("heading", { name: "Before you approve" }),
  ).toBeNull();
});

test("the gate shows the figures, the profile, the issues and the cited law", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  const gate = await screen.findByRole("region", {
    name: "Before you approve",
  });
  within(gate).getByText("Rs 1,800,000.00");
  within(gate).getByText("Rs 75,000.00");
  within(gate).getByText("2025-26");
  within(gate).getByText("Yes");
  within(gate).getByText(
    "Salary certificate uploaded 05 Nov 2026: Taxable salary is more than gross salary.",
  );
  const passages = within(gate).getByRole("list", {
    name: "Where this comes from",
  });
  expect(passages.textContent).toContain(
    "Income Tax Ordinance, 2001, §149(1), page 327",
  );
});

test("text the app wrote without the AI is marked as such", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  await screen.findByRole("region", { name: "Before you approve" });
  // Only the research step used its plain result in AT_GATE.
  expect(
    screen.getAllByText("Written by the app (the AI wasn't used)"),
  ).toHaveLength(1);
});

test("without a profile, the run sends the user to set one up first", async () => {
  mockFetch({ "GET /api/auth/me": () => ME, "GET /api/profile": noProfile });
  renderApp("/workflow", { showLocation: true });

  expect(
    await screen.findByText("Location: /profile?next=%2Fworkflow"),
  ).toBeDefined();
});

// ---- User Story 2 (T016) ----

const TAX_BODY = {
  tax_year: "2025-26",
  blocked_reason: null,
  message: null,
  salary_tax: "72000",
  surcharge: "0",
  profit_tax: "0",
  salary_balance: "-3000",
  profit_balance: "0",
  non_atl_extra_withheld: null,
  salary_credit: "75000",
  profit_credit: "0",
  steps: [
    {
      description: "Salary tax: Rs 6,000 + 11% of Rs 600,000 = Rs 72,000",
      rule_location: "First Schedule, Part I, Division I, clause (2), row 3",
      result: "72000",
    },
  ],
  label: "Not yet reviewed by a tax practitioner. Not tax advice.",
};
const RESULT_BODY = { ...TAX_BODY, passages: AT_GATE.research!.passages };
const APPROVED: Run = {
  ...AT_GATE,
  step: "result",
  approved_at: "2026-11-12T10:00:00Z",
};

function showGateFlow(approve: FakeReply = { status: 200, body: APPROVED }) {
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => ({ status: 200, body: AT_GATE }),
    "POST /api/workflow/approve": () => approve,
    "POST /api/workflow/back": () => ({
      status: 200,
      body: { ...AT_GATE, step: "document", gate: null },
    }),
    "GET /api/workflow/result": () => ({ status: 200, body: RESULT_BODY }),
    "GET /api/tax/2025-26/summary": () => ({
      status: 200,
      body: { summary: null },
    }),
    "POST /api/workflow/done": () => ({
      status: 200,
      body: { ...APPROVED, step: "done", done_at: "2026-11-12T10:05:00Z" },
    }),
  });
}

test("approving sends the fingerprint the user saw and shows the result", async () => {
  const fetch = showGateFlow();
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));

  expect(await screen.findByText("Rs 3,000 over-deducted")).toBeDefined();
  expect(fetch).toHaveBeenCalledWith(
    "/api/workflow/approve",
    expect.objectContaining({
      body: JSON.stringify({ fingerprint: AT_GATE.fingerprint }),
    }),
  );
  screen.getByText("Not yet reviewed by a tax practitioner. Not tax advice.");
  screen.getByText(/Salary tax: Rs 6,000/);
  expect(
    screen
      .getByRole("button", { name: "Download PDF" })
      .getAttribute("aria-disabled"),
  ).toBe("false");
  const sources = screen.getByRole("list", { name: "Where this comes from" });
  expect(sources.textContent).toContain("§149(1), page 327");
});

test("if the inputs changed, approving says so and the run reloads for a new look", async () => {
  const changed: Run = {
    ...AT_GATE,
    inputs_changed: true,
    fingerprint: "e".repeat(64),
  };
  let gets = 0;
  const fetch = mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => ({
      status: 200,
      body: gets++ === 0 ? AT_GATE : changed,
    }),
    "POST /api/workflow/approve": () => ({
      status: 409,
      body: { detail: "Your inputs changed; please review and approve again." },
    }),
  });
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Your inputs changed",
  );
  await screen.findByText(
    "Your inputs changed; please review and approve again.",
    {
      selector: ".notice",
    },
  );
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/workflow/approve",
      expect.objectContaining({
        body: JSON.stringify({ fingerprint: changed.fingerprint }),
      }),
    ),
  );
});

test("Go back leaves the gate", async () => {
  showGateFlow();
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Go back" }));

  expect(
    await screen.findByRole("button", { name: "Start again" }),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
});

test("marking the run done shows the date", async () => {
  showGateFlow();
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  fireEvent.click(await screen.findByRole("button", { name: "Mark done" }));

  expect(await screen.findByText("Done on 12 Nov 2026.")).toBeDefined();
  expect(screen.queryByRole("button", { name: "Mark done" })).toBeNull();
});

// ---- User Story 3 (T020) ----

test("back at the gate after an approval, the page says the inputs changed", async () => {
  showWorkflow({ ...AT_GATE, inputs_changed: true });
  renderApp("/workflow");

  expect(
    await screen.findByText(
      "Your inputs changed; please review and approve again.",
    ),
  ).toBeDefined();
});

test("a run that was never approved doesn't claim its inputs changed", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  await screen.findByRole("region", { name: "Before you approve" });
  expect(screen.queryByText(/Your inputs changed/)).toBeNull();
});

// ---- Review fixes ----

test("if the run can't be loaded, it says so and offers to try again", async () => {
  let attempts = 0;
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () =>
      attempts++ === 0
        ? { status: 500, body: { detail: "Something went wrong." } }
        : { status: 200, body: AT_GATE },
  });
  renderApp("/workflow");

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Something went wrong.",
  );
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));

  expect(
    await screen.findByRole("region", { name: "Before you approve" }),
  ).toBeDefined();
});

test("while the run loads, the page says so", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => new Promise<FakeReply>(() => {}),
  });
  renderApp("/workflow");

  expect(await screen.findByText("Loading your guided run…")).toBeDefined();
});

test("if the result is refused (inputs changed after approval), the run reloads to the gate", async () => {
  let gets = 0;
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => ({
      status: 200,
      body: gets++ === 0 ? APPROVED : { ...AT_GATE, inputs_changed: true },
    }),
    "GET /api/workflow/result": () => ({
      status: 409,
      body: { detail: "Approval needed." },
    }),
  });
  renderApp("/workflow");

  expect(
    await screen.findByText(
      "Your inputs changed; please review and approve again.",
      { selector: ".notice" },
    ),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "Approve" })).toBeDefined();
});

test("after approving, focus moves to the result", async () => {
  showGateFlow();
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));

  const heading = await screen.findByRole("heading", { name: "Your result" });
  await waitFor(() => expect(document.activeElement).toBe(heading));
});

test("after starting, focus moves to the gate", async () => {
  showWorkflow(null);
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  const heading = await screen.findByRole("heading", {
    name: "Before you approve",
  });
  await waitFor(() => expect(document.activeElement).toBe(heading));
});

test("a second click while approving sends nothing more", async () => {
  // The approval never answers, so the first click is still in progress.
  const pending = mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => ({ status: 200, body: AT_GATE }),
    "POST /api/workflow/approve": () => new Promise<FakeReply>(() => {}),
  });
  renderApp("/workflow");

  const approve = await screen.findByRole("button", { name: "Approve" });
  fireEvent.click(approve);
  fireEvent.click(approve);

  await waitFor(() =>
    expect(approve.getAttribute("aria-disabled")).toBe("true"),
  );
  const posts = pending.mock.calls.filter(
    ([path]) => path === "/api/workflow/approve",
  );
  expect(posts).toHaveLength(1);
});

test("once the steps finish, the progress stops", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  showWorkflow(null);
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));
  await screen.findByRole("region", { name: "Before you approve" });
  act(() => {
    vi.advanceTimersByTime(5000);
  });

  expect(screen.getByRole("status").textContent).toBe("");
});

test("a failed start says so and Start stays available", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () => ({
      status: 404,
      body: { detail: "No guided run yet." },
    }),
    "POST /api/workflow/start": () => ({
      status: 500,
      body: { detail: "Try later." },
    }),
  });
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Try later.",
  );
  expect(screen.getByRole("button", { name: "Start" })).toBeDefined();
});

test("with a certificate missing, Go to documents is the main action", async () => {
  showWorkflow(MISSING);
  renderApp("/workflow");

  const startAgain = await screen.findByRole("button", { name: "Start again" });
  expect(startAgain.className).not.toContain("button-primary");
});
