import { expect, request, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { apiUserWithConfirmedSalary } from "./helpers";

// The admin area (feature 011): an admin made from the command line signs in at /admin, finds a
// taxpayer and disables the account, and the taxpayer can no longer sign in to the app. The admin
// is created before the run (e2e/README.md, CI): `create-admin` with these synthetic details.

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "e2e-admin@example.com";
const ADMIN_PASSWORD =
  process.env.E2E_ADMIN_PASSWORD ?? "e2e-admin-password-not-real";
const PASSWORD = "e2e-password-not-real";

test("an admin disables a taxpayer, who can then no longer sign in", async ({
  page,
  baseURL,
}) => {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const taxpayer = await request.newContext({ baseURL });
  const signup = await taxpayer.post("/api/auth/signup", {
    data: { email, password: PASSWORD },
  });
  expect(signup.ok()).toBe(true);

  await page.goto("/admin/login");
  await page.getByLabel("Username").fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Taxpayer accounts")).toBeVisible();

  await page.goto(`/admin/account/list?q=${encodeURIComponent(email)}`);
  await page.locator('a[href*="/admin/account/detail"]').first().click();
  await expect(page.getByText("Progress")).toBeVisible();
  // The action buttons work once the page's scripts have loaded.
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Disable", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const done = page.waitForResponse((r) => r.url().includes("/row-action"));
  await dialog.getByRole("button", { name: "Yes, Proceed" }).click();
  expect((await done).status()).toBe(200);
  // Back on the account page, which now offers Re-enable instead of Disable.
  await expect(page.getByRole("button", { name: "Re-enable" })).toBeVisible();

  const login = await taxpayer.post("/api/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(login.status()).toBe(401);
  await taxpayer.dispose();
});

/** Sign in to /admin and open the account with this email. */
async function openAccount(page: Page, email: string): Promise<void> {
  await page.goto("/admin/login");
  await page.getByLabel("Username").fill(ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Taxpayer accounts")).toBeVisible();
  await page.goto(`/admin/account/list?q=${encodeURIComponent(email)}`);
  await page.locator('a[href*="/admin/account/detail"]').first().click();
  await expect(page.getByText("Progress")).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test("an admin deletes an account with a confirmed certificate", async ({
  page,
  baseURL,
}) => {
  // A taxpayer with an uploaded, read (fake Gemini) and confirmed salary certificate.
  const email = await apiUserWithConfirmedSalary(page);

  await openAccount(page, email);
  await expect(page.getByText("salary_certificate")).toBeVisible();
  await expect(page.getByText(/Rs 72,000/)).toBeVisible(); // the tax result, as the Tax page
  await page
    .getByRole("button", { name: "Delete account", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const done = page.waitForResponse((r) => r.url().includes("/row-action"));
  await dialog.getByRole("button", { name: "Yes, Proceed" }).click();
  expect((await done).status()).toBe(200);

  await page.goto("/admin/document/list");
  await expect(page.getByText(email)).toHaveCount(0); // the document went with the account
  const taxpayer = await request.newContext({ baseURL });
  const login = await taxpayer.post("/api/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(login.status()).toBe(401);
  await taxpayer.dispose();
});
