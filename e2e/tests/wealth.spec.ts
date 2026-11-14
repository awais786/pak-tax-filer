import { expect, test } from "@playwright/test";
import { LABEL, apiUserWithConfirmedSalary } from "./helpers";

// The wealth statement: the salary certificate's figures fill it in, the user adds last year's
// net assets, saves, and gets a labelled result and its PDF.

test("a saved statement gives a labelled result and its PDF", async ({
  page,
}) => {
  await apiUserWithConfirmedSalary(page);

  await page.goto("/wealth");
  await page.getByLabel(/net assets on 30 june 2025/i).fill("1000000");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  const result = page.getByRole("region", { name: "Result" });
  await expect(result.getByText(LABEL)).toBeVisible();
  const download = page.waitForEvent("download");
  await result.getByRole("button", { name: "Download PDF" }).click();
  expect((await download).suggestedFilename()).toBe("wealth-2025-26.pdf");
});
