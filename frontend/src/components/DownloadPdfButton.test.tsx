import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { mockFetch } from "../test/mockFetch";
import { DownloadPdfButton } from "./DownloadPdfButton";

// The PDF download (feature 008, task T005; contracts/pdf-and-telemetry.md). The PDF is made by
// the backend with the practitioner label on every page; this only fetches and saves it, says
// why it failed, or says why it can't be had.

const URL_ = "/api/tax/2025-26/pdf";
let saved: { name: string; href: string }[] = [];

beforeEach(() => {
  saved = [];
  // jsdom has no blob addresses; the browser's are only handed to the download link.
  URL.createObjectURL = vi.fn(() => "blob:the-pdf");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved.push({ name: this.download, href: this.href });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("downloads the PDF under the name the server gives it", async () => {
  const fetch = vi.fn(
    async () =>
      new Response(new Blob(["%PDF-1.7"]), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="tax-2025-26.pdf"',
        },
      }),
  );
  vi.stubGlobal("fetch", fetch);
  render(<DownloadPdfButton url={URL_} disabledReason={null} />);

  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

  await vi.waitFor(() => expect(saved).toHaveLength(1));
  expect(fetch).toHaveBeenCalledWith(URL_, expect.anything());
  expect(saved).toEqual([{ name: "tax-2025-26.pdf", href: "blob:the-pdf" }]);
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a refusal after the page loaded is shown, and nothing is saved", async () => {
  mockFetch({
    [`GET ${URL_}`]: () => ({
      status: 409,
      body: { detail: "Approval needed." },
    }),
  });
  render(<DownloadPdfButton url={URL_} disabledReason={null} />);

  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Approval needed.",
  );
  expect(saved).toEqual([]);
});

test("when the result can't be exported, it says why and fetches nothing", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <DownloadPdfButton
      url={URL_}
      disabledReason="Upload and confirm a salary certificate first."
    />,
  );

  const button = screen.getByRole("button", {
    name: "Download PDF",
    description: "Upload and confirm a salary certificate first.",
  });
  expect(button.getAttribute("aria-disabled")).toBe("true");
  fireEvent.click(button);
  expect(fetch).not.toHaveBeenCalled();
});
