import { expect, test } from "@playwright/test";
import { LABEL, apiUserWithConfirmedSalary } from "./helpers";

// Guided filing: the checks run, the run stops for approval, and only then is the result shown
// (constitution, Principle III).

test("a guided run stops for approval, then shows the result", async ({
  page,
}) => {
  await apiUserWithConfirmedSalary(page);

  await page.goto("/workflow");
  await page.getByRole("button", { name: "Start" }).click();
  await expect(
    page.getByRole("heading", { name: "Before you approve" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your result" })).toHaveCount(
    0,
  );

  await page.getByRole("button", { name: "Approve" }).click();
  await expect(
    page.getByRole("heading", { name: "Your result" }),
  ).toBeVisible();
  await expect(page.getByText(LABEL)).toBeVisible();

  await page.getByRole("button", { name: "Mark done" }).click();
  await expect(page.getByText(/^Done on /)).toBeVisible();
});
