import { defineConfig, devices } from "@playwright/test";

// The end-to-end tests (README.md): the app at E2E_BASE_URL, started by docker-compose.e2e.yml
// with a fake Gemini. Chromium only; each test signs up its own user, so tests run in parallel.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  // No retries: a flaky test must show, not pass on a second try (review, PR #44).
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    // The e2e stack's own port (docker-compose.e2e.yml), so it runs beside development.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:15173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
