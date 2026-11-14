import { expect, test } from "@playwright/test";
import {
  confirmEveryFigure,
  LABEL,
  signUpWithProfile,
  uploadSalaryCertificate,
} from "./helpers";

// The main flow (the one that broke for the lead on 2026-11-12): sign up, set the profile,
// upload a salary certificate, confirm its figures, see the tax and download its PDF.

test("a confirmed salary certificate gives the tax result and its PDF", async ({
  page,
}) => {
  // The whole path through the UI, on purpose: the other tests set this up through the API.
  await signUpWithProfile(page);
  await uploadSalaryCertificate(page);
  await confirmEveryFigure(page);

  await page.goto("/tax");
  await expect(
    page.getByRole("heading", { name: "Your tax for 2025-26" }),
  ).toBeVisible();
  await expect(page.getByText(LABEL)).toBeVisible();
  // Rs 1,800,000 taxable: 6,000 + 11% of 600,000 = Rs 72,000; Rs 75,000 deducted.
  await expect(page.getByText("Rs 72,000").first()).toBeVisible();
  // The headline (the breakdown says it too).
  await expect(page.getByText("Rs 3,000 over-deducted").first()).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  expect((await download).suggestedFilename()).toBe("tax-2025-26.pdf");
});
