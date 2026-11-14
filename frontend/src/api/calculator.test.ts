import { afterEach, expect, test, vi } from "vitest";
import { calculateTax } from "./calculator";
import { mockFetch } from "../test/mockFetch";

// The calculator call (feature 010, task T013), per
// specs/010-income-tax-engine/contracts/calculator-api.md.

afterEach(() => {
  vi.unstubAllGlobals();
});

test("posts the typed amounts as JSON and returns the result", async () => {
  let sent: unknown = null;
  const fake = mockFetch({
    "POST /api/tax/calculator": ({ body }) => {
      sent = body;
      return {
        status: 200,
        body: { tax_year: "2025-26", total_tax: "1107600" },
      };
    },
  });

  const result = await calculateTax({
    salary_monthly: "250000",
    rent_monthly: "140000",
  });

  expect(sent).toEqual({ salary_monthly: "250000", rent_monthly: "140000" });
  expect(fake).toHaveBeenCalledOnce();
  expect(result.total_tax).toBe("1107600");
});
