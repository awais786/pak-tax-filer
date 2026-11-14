import { expect, test } from "@playwright/test";
import {
  signUpWithProfile,
  syntheticPdf,
  uploadSalaryCertificate,
} from "./helpers";

// When Google doesn't answer in time (its 504, which the lead hit on 2026-11-12), the upload
// says so plainly, keeps the file for Retry, and doesn't charge the try (PR #43).

test("an upload Google times out on says so and offers Retry", async ({
  page,
}) => {
  await signUpWithProfile(page);

  await uploadSalaryCertificate(page, syntheticPdf("E2E-GOOGLE-TIMEOUT"));

  // Said where the upload was made (the list says it too, beside Retry).
  const alert = page.getByRole("alert");
  await expect(alert).toContainText(
    "Google's AI service is busy and didn't answer in time",
  );
  await expect(alert).toContainText(
    "This try doesn't count toward your daily limit",
  );
  await expect(page.getByRole("button", { name: /Retry/ })).toBeVisible();
});
