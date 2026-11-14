import { expect, test } from "@playwright/test";
import { LABEL, signUpWithProfile } from "./helpers";

// The simple tax calculator (feature 010, task T021): the lead's example, typed in, gives his
// tax. No AI is used, so the fake Gemini plays no part.

test("salary 250,000 and rent 140,000 a month give Rs 1,107,600", async ({
  page,
}) => {
  await signUpWithProfile(page);

  await page.goto("/calculator");
  await page.getByLabel("Salary per month").fill("250000");
  await page.getByLabel("Rent per month").fill("140000");
  await page.getByRole("button", { name: "Calculate" }).click();

  await expect(page.getByRole("heading", { name: "Your tax" })).toBeVisible();
  await expect(page.getByText(LABEL)).toBeVisible();
  // Research R1: rent less one-fifth is slab income; salary is 69.06% of 4,344,000, not more
  // than 75%, so the non-salaried table: 650,000 + 40% of 1,144,000.
  await expect(page.getByText("Rs 1,107,600").first()).toBeVisible();
  // The summary line and the breakdown's step both say so.
  await expect(page.getByText(/non-salaried table/).first()).toBeVisible();
  // Take-home pay after the employer's monthly deduction on the salary alone (s.149).
  const monthly = page.getByRole("region", { name: "Each month" });
  await expect(monthly.getByText("Rs 225,000", { exact: true })).toBeVisible();
});
