import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { CalculatorResult } from "../api/calculator";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The simple tax calculator (feature 010, tasks T014, T017, T020), per
// specs/010-income-tax-engine/contracts/calculator-api.md. Figures are shown as the API gives
// them; the page does no tax maths (Principle I).

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
const NOT_COVERED = [
  "Tax already deducted, and whether you owe more or get a refund",
];

// The lead's example (research R1): salary 250,000 and rent 140,000 a month.
const LEAD: CalculatorResult = {
  tax_year: "2025-26",
  blocked_reason: null,
  message: null,
  incomes: [
    {
      source: "salary",
      yearly_amount: "3000000",
      taxable_amount: "3000000",
      treatment: "slab",
    },
    {
      source: "rent",
      yearly_amount: "1680000",
      taxable_amount: "1344000",
      treatment: "slab",
    },
  ],
  taxable_income: "4344000",
  salary_share: "69.06",
  table: "non_salaried",
  slab_tax: "1107600",
  surcharge: "0",
  dividend_tax: "0",
  profit_tax: "0",
  total_tax: "1107600",
  effective_rate: "23.7",
  monthly: { salary_tax: "25000", take_home: "225000" },
  bonus_impact: null,
  filer_comparison: [],
  on_atl: true,
  steps: [
    {
      description:
        "Property income: rent Rs 1,680,000 less the repairs allowance of one-fifth, Rs 336,000 = Rs 1,344,000",
      rule_location:
        "Income Tax Ordinance, 2001 (amended up to 31.07.2025), Section 15A(1)(a) (p. 57, PDF p. 76); effective 2025-07-01",
      result: "1344000",
    },
  ],
  not_covered: NOT_COVERED,
  label: LABEL,
};

const DIVIDEND_LINE = {
  source: "dividends" as const,
  your_rate: "15",
  other_rate: "30",
  your_deduction: "150000",
  other_deduction: "300000",
  difference: "150000",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Open the calculator with the backend answering `reply`; returns what was posted. */
function openCalculator(reply: Partial<CalculatorResult> | FakeReply) {
  const posted: unknown[] = [];
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/tax/calculator": ({ body }) => {
      posted.push(body);
      return "status" in reply && typeof reply.status === "number"
        ? (reply as FakeReply)
        : { status: 200, body: { ...LEAD, ...reply } };
    },
  });
  renderApp("/calculator");
  return posted;
}

async function type(label: RegExp, value: string) {
  fireEvent.change(await screen.findByLabelText(label), {
    target: { value },
  });
}

async function calculate() {
  fireEvent.click(await screen.findByRole("button", { name: /calculate/i }));
  return screen.findByRole("heading", { name: /your tax/i });
}

test("is a main landmark asking for the five amounts, not tax year or ATL status", async () => {
  openCalculator({});

  for (const label of [
    /salary per month/i,
    /bonus for the year/i,
    /rent per month/i,
    /dividends for the year/i,
    /bank profit for the year/i,
  ]) {
    expect(await screen.findByLabelText(label)).toBeTruthy();
  }
  expect(screen.getByRole("main")).toBeTruthy();
  expect(screen.queryByLabelText(/tax year/i)).toBeNull();
  expect(screen.queryByLabelText(/atl|filer/i)).toBeNull();
});

test("posts only the amounts typed, leaving out cleared and blank fields", async () => {
  const posted = openCalculator({});
  await type(/salary per month/i, "250000");
  await type(/rent per month/i, "140000");
  await type(/bonus for the year/i, "5000");
  await type(/bonus for the year/i, "");
  await type(/dividends for the year/i, "   ");

  await calculate();

  expect(posted).toEqual([
    { salary_monthly: "250000", rent_monthly: "140000" },
  ]);
});

test("shows the result as given, and moves focus to it", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  const heading = await calculate();

  await waitFor(() => expect(document.activeElement).toBe(heading));
  const total = screen.getByText("Total tax").closest("div")!;
  expect(within(total).getByText("Rs 1,107,600")).toBeTruthy();
  expect(screen.getByText(/23\.7% of your income/)).toBeTruthy();
  expect(screen.getByText(/non-salaried table applies/i)).toBeTruthy();
  expect(screen.getByText(/69\.06%/)).toBeTruthy();
  expect(screen.getByText("Rs 4,344,000")).toBeTruthy();
  expect(screen.getByText(LABEL)).toBeTruthy();
});

test("lists each income's yearly amount, and rent's taxed amount", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  await calculate();

  const salary = screen.getByText(/^Salary \(/).closest("div")!;
  expect(salary.textContent).toContain("Rs 3,000,000");
  expect(salary.textContent).not.toMatch(/taxed on/);
  const rent = screen.getByText(/^Rent \(/).closest("div")!;
  expect(rent.textContent).toContain("Rs 1,680,000");
  expect(rent.textContent).toContain("taxed on Rs 1,344,000");
});

test("shows the slab tax but hides tax lines with nothing due", async () => {
  openCalculator({ slab_tax: "0", total_tax: "0", effective_rate: "0.0" });
  await type(/salary per month/i, "40000");

  await calculate();

  expect(screen.getByText("Tax on taxable income")).toBeTruthy();
  expect(screen.queryByText("Surcharge")).toBeNull();
  expect(screen.queryByText("Tax on dividends")).toBeNull();
  expect(screen.queryByText("Tax on bank profit")).toBeNull();
});

test("shows the monthly deduction and take-home, saying the rest is settled with the return", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  await calculate();

  const monthly = screen.getByRole("region", { name: /each month/i });
  expect(within(monthly).getByText("Rs 25,000")).toBeTruthy();
  expect(within(monthly).getByText("Rs 225,000")).toBeTruthy();
  expect(within(monthly).getByText(/settled with your return/i)).toBeTruthy();
});

test("shows no monthly view or bonus line when the API sends none", async () => {
  openCalculator({ monthly: null, bonus_impact: null });
  await type(/rent per month/i, "140000");

  await calculate();

  expect(screen.queryByRole("region", { name: /each month/i })).toBeNull();
  expect(screen.queryByText(/your bonus/i)).toBeNull();
});

test("says what the bonus adds", async () => {
  openCalculator({ bonus_impact: "86000" });
  await type(/salary per month/i, "200000");
  await type(/bonus for the year/i, "1300000");

  await calculate();

  expect(screen.getByText(/your bonus/i).textContent).toBe(
    "Your bonus adds Rs 86,000 to your tax.",
  );
});

test("says when the bonus lowers the tax, never 'adds' a minus", async () => {
  openCalculator({ bonus_impact: "-429000" });
  await type(/salary per month/i, "300000");
  await type(/bonus for the year/i, "1");

  await calculate();

  const line = screen.getByText(/your bonus/i).textContent ?? "";
  expect(line).toContain("lowers your tax by Rs 429,000");
  expect(line).not.toMatch(/adds|-/);
});

test("shows dividend tax and the filer comparison as deductions, never a refund", async () => {
  openCalculator({
    dividend_tax: "150000",
    filer_comparison: [DIVIDEND_LINE],
  });
  await type(/dividends for the year/i, "1000000");

  await calculate();

  const tax = screen.getByText("Tax on dividends").closest("div")!;
  expect(within(tax).getByText("Rs 150,000")).toBeTruthy();
  const comparison = screen.getByRole("region", { name: /filer/i });
  expect(comparison.textContent).toContain(
    "Rs 150,000 deducted at 15% for you (on the ATL)",
  );
  expect(comparison.textContent).toContain(
    "Rs 300,000 at 30% for someone not on the ATL",
  );
  expect(within(comparison).getByText(/tax itself is the same/i)).toBeTruthy();
  expect(comparison.textContent).not.toMatch(/refund/i);
});

test("words the comparison by the ATL status the API used", async () => {
  openCalculator({
    dividend_tax: "150000",
    on_atl: false,
    filer_comparison: [
      {
        ...DIVIDEND_LINE,
        your_rate: "30",
        other_rate: "15",
        your_deduction: "300000",
        other_deduction: "150000",
      },
    ],
  });
  await type(/dividends for the year/i, "1000000");

  await calculate();

  const comparison = screen.getByRole("region", { name: /filer/i });
  expect(comparison.textContent).toContain(
    "Rs 300,000 deducted at 30% for you (not on the ATL)",
  );
  expect(comparison.textContent).toContain("for someone on the ATL");
});

test("lists every step with its source, and what isn't covered", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  await calculate();

  const steps = screen.getByRole("list", { name: /how it was worked out/i });
  expect(within(steps).getByText(/repairs allowance/i)).toBeTruthy();
  expect(within(steps).getByText(/effective 2025-07-01/)).toBeTruthy();
  const notCovered = screen.getByRole("region", { name: /not covered/i });
  expect(within(notCovered).getByText(NOT_COVERED[0])).toBeTruthy();
});

test("clears the result when an amount changes, so it never shows stale figures", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");
  await calculate();

  await type(/salary per month/i, "260000");

  expect(screen.queryByRole("heading", { name: /your tax/i })).toBeNull();
});

test("a refusal shows its message and no figures", async () => {
  openCalculator({
    blocked_reason: "no_income",
    message: "Enter at least one income above zero.",
    incomes: [],
    taxable_income: null,
    salary_share: null,
    table: null,
    slab_tax: null,
    surcharge: null,
    dividend_tax: null,
    profit_tax: null,
    total_tax: null,
    effective_rate: null,
    monthly: null,
    steps: [],
  });

  await calculate();

  expect(
    screen.getByText("Enter at least one income above zero."),
  ).toBeTruthy();
  expect(screen.queryByText("Total tax")).toBeNull();
  expect(screen.queryByRole("region", { name: /each month/i })).toBeNull();
  expect(screen.getByText(LABEL)).toBeTruthy();
});

test("an invalid amount shows the server's reason against the field's label", async () => {
  openCalculator({
    status: 422,
    body: {
      detail: [
        {
          loc: ["body", "salary_monthly"],
          msg: "Value error, must be rupees written as a string of digits",
          type: "value_error",
        },
      ],
    },
  });
  await type(/salary per month/i, "12x");

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Salary per month");
  expect(alert.textContent).toContain("must be rupees");
  expect(
    screen
      .getByRole("button", { name: /calculate/i })
      .getAttribute("aria-describedby"),
  ).toBe(alert.id);
  expect(screen.queryByRole("heading", { name: /your tax/i })).toBeNull();
});

test("a server failure says to try again", async () => {
  openCalculator({ status: 500, body: { detail: "Internal Server Error" } });
  await type(/salary per month/i, "250000");

  fireEvent.click(screen.getByRole("button", { name: /calculate/i }));

  expect((await screen.findByRole("alert")).textContent).toMatch(/try again/i);
  expect(screen.queryByRole("heading", { name: /your tax/i })).toBeNull();
});
