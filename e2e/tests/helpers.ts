import { expect, type APIResponse, type Page } from "@playwright/test";

// Steps the end-to-end tests share. Elements are found as a user finds them (role, label, text),
// as in the frontend's own tests. Every user and file is synthetic (constitution, Principle V).

const PASSWORD = "e2e-password-not-real";

/** A one-page PDF made here, never a real document; `marker` goes in its title (the fake Gemini
 * answers a file with E2E-GOOGLE-TIMEOUT in it with Google's 504). */
export function syntheticPdf(marker = "E2E synthetic certificate"): Buffer {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
    `<< /Title (${marker}) >>`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets
    .map((at) => `${String(at).padStart(10, "0")} 00000 n \n`)
    .join("");
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R /Info 4 0 R >>\n`;
  pdf += `startxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

/** A fresh synthetic email for one test. */
function newEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

/** Sign up a fresh user and set their profile (tax year 2025-26, on the ATL), through the UI. */
export async function signUpWithProfile(page: Page): Promise<void> {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(newEmail());
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Confirm password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/profile/);
  await page.getByLabel("Tax year").selectOption("2025-26");
  await page.getByRole("radio", { name: "Yes" }).check();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page).not.toHaveURL(/\/profile/);
}

/** Upload a salary certificate through the UI: its review page follows, or, if reading failed,
 * the reason on the Documents page. */
export async function uploadSalaryCertificate(
  page: Page,
  pdf = syntheticPdf(),
): Promise<void> {
  await page.goto("/documents");
  await page.getByLabel("Document type").selectOption("salary_certificate");
  await page.getByLabel(/^File \(PDF/).setInputFiles({
    name: "salary-certificate.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await page.getByRole("button", { name: "Upload" }).click();
}

/** Confirm each figure the AI read, then the document, through the UI. */
export async function confirmEveryFigure(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: /Check the figures/ }),
  ).toBeVisible();
  for (const field of [
    "tax year",
    "gross salary",
    "taxable salary",
    "tax deducted",
  ]) {
    await page.getByRole("button", { name: `Confirm ${field}` }).click();
  }
  // Then the document as a whole, once every figure's save has landed: only now can its
  // figures be used (Principle III).
  await expect(page.getByText("Confirmed.", { exact: true })).toHaveCount(4);
  await page.getByRole("button", { name: "Confirm document" }).click();
  await expect(page.getByText(/This document is confirmed/)).toBeVisible();
}

/** The same user and confirmed certificate set up through the API, for tests about later pages
 * (tax.spec.ts proves the UI path). `page.request` shares the page's cookies, so the browser is
 * then logged in as this user. Rs 1,800,000 taxable, Rs 75,000 deducted. */
export async function apiUserWithConfirmedSalary(page: Page): Promise<void> {
  const api = page.request;
  const ok = async (response: Promise<APIResponse>) => {
    const reply = await response;
    expect(reply.ok(), `${reply.url()}: ${reply.status()}`).toBe(true);
    return reply;
  };
  await ok(
    api.post("/api/auth/signup", {
      data: { email: newEmail(), password: PASSWORD },
    }),
  );
  await ok(
    api.put("/api/profile", { data: { tax_year: "2025-26", on_atl: true } }),
  );
  const uploaded = await ok(
    api.post("/api/documents", {
      multipart: {
        doc_type: "salary_certificate",
        file: {
          name: "salary-certificate.pdf",
          mimeType: "application/pdf",
          buffer: syntheticPdf(),
        },
      },
    }),
  );
  const { id } = (await uploaded.json()) as { id: string };
  for (const name of [
    "tax_year",
    "gross_salary",
    "taxable_salary",
    "tax_deducted",
  ]) {
    await ok(
      api.patch(`/api/documents/${id}/fields/${name}`, {
        data: { confirmed: true },
      }),
    );
  }
  await ok(api.post(`/api/documents/${id}/confirm`, { data: {} }));
}

export const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
