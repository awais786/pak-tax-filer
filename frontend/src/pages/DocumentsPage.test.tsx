import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { DocumentSummary } from "../api/documents";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeRoutes } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Upload and the document list, per specs/003-document-extraction/contracts/documents-api.md
// (tasks T015, T023; spec User Stories 1 and 3).

const ME = { status: 200, body: { email: "demo@example.com" } };

const SUMMARY: DocumentSummary = {
  id: "d1",
  doc_type: "salary_certificate",
  tax_year: "2025-26",
  status: "needs_review",
  failure_reason: null,
  media_type: "application/pdf",
  page_count: 1,
  created_at: "2026-11-05T10:00:00Z",
  confirmed_at: null,
};
const FAILED: DocumentSummary = {
  ...SUMMARY,
  id: "d2",
  doc_type: "bank_profit_certificate",
  status: "failed",
  failure_reason: "The AI service is busy. Try again in a minute.",
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function routes(extra: FakeRoutes = {}): FakeRoutes {
  return {
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/documents": () => ({ status: 200, body: [] }),
    ...extra,
  };
}

function chooseFile(name = "certificate.pdf") {
  const input = screen.getByLabelText(/file/i);
  const file = new File(["%PDF-1.7 synthetic"], name, {
    type: "application/pdf",
  });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

function chooseType(label: RegExp) {
  fireEvent.change(screen.getByLabelText(/document type/i), {
    target: {
      value: /salary/i.test(label.source)
        ? "salary_certificate"
        : "bank_profit_certificate",
    },
  });
}

test("the upload page says to use demo data only", async () => {
  mockFetch(routes());
  renderApp("/documents");

  await screen.findByText(/demo data only/i);
  screen.getByText(/do not upload real documents/i);
});

test("the document type must be chosen before uploading", async () => {
  const fetch = mockFetch(routes());
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /choose the document type/i,
  );
  expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
    false,
  );
});

test("progress is shown while the document is being read", async () => {
  mockFetch(routes({ "POST /api/documents": () => new Promise(() => {}) }));
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("status")).textContent).toMatch(
    /reading the document/i,
  );
  expect(
    screen.getByRole("button", { name: /upload/i }) as
      HTMLButtonElement | HTMLInputElement,
  ).toHaveProperty("disabled", true);
});

test.each([
  [413, "The file is over 10 MB."],
  [415, "Only PDF, JPG or PNG files can be uploaded."],
  [422, "The PDF has 6 pages; the limit is 5 pages."],
])(
  "a refused upload (%i) shows the server's reason",
  async (status, detail) => {
    mockFetch(
      routes({ "POST /api/documents": () => ({ status, body: { detail } }) }),
    );
    renderApp("/documents");
    await screen.findByRole("heading", { level: 1, name: /documents/i });

    chooseType(/salary/);
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: /upload/i }));

    expect((await screen.findByRole("alert")).textContent).toContain(detail);
  },
);

test("a successful upload sends the file and type, then opens its review page", async () => {
  let sent: unknown = null;
  mockFetch(
    routes({
      "POST /api/documents": ({ body }) => {
        sent = body;
        return { status: 201, body: { ...SUMMARY, fields: [] } };
      },
      "GET /api/documents/d1": () => ({
        status: 200,
        body: { ...SUMMARY, fields: [] },
      }),
    }),
  );
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  const file = chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  await screen.findByRole("heading", { level: 1, name: /check the figures/i });
  expect(sent).toBeInstanceOf(FormData);
  expect((sent as FormData).get("doc_type")).toBe("salary_certificate");
  expect((sent as FormData).get("file")).toBe(file);
});

test("the list shows each document's type and status, with failed ones' reasons", async () => {
  mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [SUMMARY, FAILED] }),
    }),
  );
  renderApp("/documents");

  const salary = await screen.findByRole("row", {
    name: /salary certificate/i,
  });
  within(salary).getByText(/ready to review/i);
  expect(
    within(salary)
      .getByRole("link", { name: /review/i })
      .getAttribute("href"),
  ).toBe("/documents/d1");
  const bank = screen.getByRole("row", { name: /bank profit certificate/i });
  within(bank).getByText(/the ai service is busy/i);
});

test("a failed document can be retried, and the list refreshes", async () => {
  let current = [FAILED];
  const fetch = mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: current }),
      "POST /api/documents/d2/retry": () => {
        current = [{ ...FAILED, status: "needs_review", failure_reason: null }];
        return { status: 200, body: { ...current[0], fields: [] } };
      },
    }),
  );
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /bank profit/i });
  fireEvent.click(within(row).getByRole("button", { name: /retry/i }));

  await screen.findByText(/ready to review/i);
  expect(
    fetch.mock.calls.some(
      ([path, init]) =>
        path === "/api/documents/d2/retry" && init?.method === "POST",
    ),
  ).toBe(true);
});

test("deleting asks first, then removes the document", async () => {
  let current = [SUMMARY];
  mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: current }),
      "DELETE /api/documents/d1": () => {
        current = [];
        return { status: 204 };
      },
    }),
  );
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /salary certificate/i });
  fireEvent.click(within(row).getByRole("button", { name: /delete/i }));

  expect(confirm).toHaveBeenCalled();
  await waitFor(() =>
    expect(
      screen.queryByRole("row", { name: /salary certificate/i }),
    ).toBeNull(),
  );
});

test("cancelling the delete question keeps the document", async () => {
  const fetch = mockFetch(
    routes({ "GET /api/documents": () => ({ status: 200, body: [SUMMARY] }) }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(false);
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /salary certificate/i });
  fireEvent.click(within(row).getByRole("button", { name: /delete/i }));

  expect(fetch.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(
    false,
  );
});

// Frontend review findings (2026-11-05).

test("a file must be chosen before uploading", async () => {
  const fetch = mockFetch(routes());
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /choose a file/i,
  );
  expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
    false,
  );
});

test("the list shows when each document was uploaded, and View for confirmed ones", async () => {
  const confirmed: DocumentSummary = {
    ...SUMMARY,
    id: "d3",
    doc_type: "bank_profit_certificate",
    status: "confirmed",
    confirmed_at: "2026-11-05T11:00:00Z",
  };
  mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [SUMMARY, confirmed] }),
    }),
  );
  renderApp("/documents");

  const salary = await screen.findByRole("row", {
    name: /salary certificate/i,
  });
  within(salary).getByText(new Date(SUMMARY.created_at).toLocaleString());
  const bank = screen.getByRole("row", { name: /bank profit certificate/i });
  expect(
    within(bank).getByRole("link", { name: /view/i }).getAttribute("href"),
  ).toBe("/documents/d3");
});

test("a list that can't be loaded says so", async () => {
  mockFetch(
    routes({
      "GET /api/documents": () => ({
        status: 500,
        body: { detail: "Database down." },
      }),
    }),
  );
  renderApp("/documents");

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Database down.",
  );
});

test("a failed retry keeps its message after the list refreshes", async () => {
  const fetch = mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [FAILED] }),
      "POST /api/documents/d2/retry": () => ({
        status: 409,
        body: { detail: "Only a failed extraction can be retried." },
      }),
    }),
  );
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /bank profit/i });
  fireEvent.click(within(row).getByRole("button", { name: /retry/i }));

  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([path]) => path === "/api/documents").length,
    ).toBeGreaterThanOrEqual(2),
  );
  expect(screen.getByRole("alert").textContent).toContain(
    "Only a failed extraction can be retried.",
  );
});

test("a failed delete keeps its message after the list refreshes", async () => {
  const fetch = mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [SUMMARY] }),
      "DELETE /api/documents/d1": () => ({
        status: 404,
        body: { detail: "Document not found." },
      }),
    }),
  );
  vi.spyOn(window, "confirm").mockReturnValue(true);
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /salary certificate/i });
  fireEvent.click(within(row).getByRole("button", { name: /delete/i }));

  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([path]) => path === "/api/documents").length,
    ).toBeGreaterThanOrEqual(2),
  );
  expect(screen.getByRole("alert").textContent).toContain(
    "Document not found.",
  );
});

test("a retry shows progress and can't be started twice", async () => {
  mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [FAILED] }),
      "POST /api/documents/d2/retry": () => new Promise(() => {}),
    }),
  );
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /bank profit/i });
  const retry = within(row).getByRole("button", { name: /retry/i });
  fireEvent.click(retry);

  expect((await screen.findByRole("status")).textContent).toMatch(
    /reading the document/i,
  );
  expect(retry).toHaveProperty("disabled", true);
});

test("each row's buttons say which document they are for", async () => {
  mockFetch(
    routes({ "GET /api/documents": () => ({ status: 200, body: [SUMMARY] }) }),
  );
  renderApp("/documents");

  await screen.findByRole("button", {
    name: /delete salary certificate uploaded/i,
  });
});

// Task T046 (FR-005a): only a document ready to review opens the review page.

test("a failed extraction stays on this page with the reason and lists the document", async () => {
  let listed: DocumentSummary[] = [];
  const failedDocument = {
    ...FAILED,
    id: "d9",
    doc_type: "salary_certificate" as const,
    failure_reason:
      "Google's AI service is busy and didn't answer in time. Your file is saved: press Retry in a minute. This try doesn't count toward your daily limit.",
  };
  const fetch = mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: listed }),
      "POST /api/documents": () => {
        listed = [failedDocument];
        return { status: 201, body: { ...failedDocument, fields: [] } };
      },
    }),
  );
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Google's AI service is busy and didn't answer in time. Your file is saved: press Retry in a minute. This try doesn't count toward your daily limit.",
  );
  screen.getByRole("heading", { level: 1, name: /^documents$/i });
  await screen.findByRole("row", { name: /salary certificate/i });
  expect(
    fetch.mock.calls.filter(([p]) => p === "/api/documents").length,
  ).toBeGreaterThanOrEqual(3); // load, the upload, then the refresh
});

test("a wrong-type refusal keeps the chosen type so the user can fix it and upload again", async () => {
  mockFetch(
    routes({
      "POST /api/documents": () => ({
        status: 422,
        body: {
          detail: `This doesn't look like a salary certificate. It may be a bank profit certificate: if it is, choose "Bank profit certificate" as the type and upload it again.`,
        },
      }),
    }),
  );
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /may be a bank profit certificate/i,
  );
  expect(screen.getByLabelText(/document type/i)).toHaveProperty(
    "value",
    "salary_certificate",
  );
  expect(screen.getByRole("button", { name: /upload/i })).toHaveProperty(
    "disabled",
    false,
  );
});

// Feature 003 FR-017 (002 task T050): the daily extraction limit.
const DAILY_LIMIT =
  "Daily limit reached: 10 extractions per 24 hours. Try again later.";

test("an upload over the daily limit shows why", async () => {
  mockFetch(
    routes({
      "POST /api/documents": () => ({
        status: 429,
        body: { detail: DAILY_LIMIT },
      }),
    }),
  );
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  chooseFile();
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  expect((await screen.findByRole("alert")).textContent).toBe(DAILY_LIMIT);
});

test("a retry over the daily limit shows why", async () => {
  mockFetch(
    routes({
      "GET /api/documents": () => ({ status: 200, body: [FAILED] }),
      "POST /api/documents/d2/retry": () => ({
        status: 429,
        body: { detail: DAILY_LIMIT },
      }),
    }),
  );
  renderApp("/documents");

  const row = await screen.findByRole("row", { name: /bank profit/i });
  fireEvent.click(within(row).getByRole("button", { name: /retry/i }));

  expect((await screen.findByRole("alert")).textContent).toBe(DAILY_LIMIT);
});

// Feature 001, User Story 6, task T061 (FR-032): a drop area and a helpful empty list.

test("a file dropped on the upload area is the one uploaded, and its name is shown", async () => {
  let sent: unknown = null;
  mockFetch(
    routes({
      "POST /api/documents": ({ body }) => {
        sent = body;
        return { status: 201, body: { ...SUMMARY, fields: [] } };
      },
      "GET /api/documents/d1": () => ({
        status: 200,
        body: { ...SUMMARY, fields: [] },
      }),
    }),
  );
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  chooseType(/salary/);
  const file = new File(["%PDF-1.7 synthetic"], "dropped.pdf", {
    type: "application/pdf",
  });
  fireEvent.drop(screen.getByLabelText(/file/i), {
    dataTransfer: { files: [file] },
  });
  screen.getByText("dropped.pdf");
  fireEvent.click(screen.getByRole("button", { name: /upload/i }));

  await screen.findByRole("heading", { level: 1, name: /check the figures/i });
  expect((sent as FormData).get("file")).toBe(file);
});

test("with no documents, the list says how to begin", async () => {
  mockFetch(routes());
  renderApp("/documents");

  await screen.findByText("No documents yet.");
  screen.getByText("Upload your salary certificate to begin.");
});

test("a drop clears any file chosen earlier in the file field, so only the dropped one counts", async () => {
  mockFetch(routes());
  renderApp("/documents");
  await screen.findByRole("heading", { level: 1, name: /documents/i });

  const input = screen.getByLabelText(/file/i) as HTMLInputElement;
  const value = vi.spyOn(input, "value", "set");
  fireEvent.drop(input, {
    dataTransfer: {
      files: [new File(["x"], "dropped.pdf", { type: "application/pdf" })],
    },
  });

  expect(value).toHaveBeenCalledWith("");
});
