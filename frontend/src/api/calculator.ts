// The simple tax calculator (feature 010), per
// specs/010-income-tax-engine/contracts/calculator-api.md. Money travels as decimal strings and
// is only displayed, never calculated with (constitution, Principle I).

import { apiFetch } from "./client";
import type { TaxStep } from "./tax";

/** What the user typed; any amount left out counts as zero. */
export type CalculatorInput = Partial<
  Record<
    "salary_monthly" | "bonus" | "rent_monthly" | "dividends" | "bank_profit",
    string
  >
>;

export type IncomeLine = {
  source: "salary" | "bonus" | "rent" | "dividends" | "bank_profit";
  yearly_amount: string;
  /** Rent after the one-fifth repairs allowance; otherwise the yearly amount. */
  taxable_amount: string;
  treatment: "slab" | "final" | "separate";
};

/** Tax deducted at source at each ATL status; the tax itself is the same for both. */
export type FilerLine = {
  source: "dividends" | "bank_profit";
  your_rate: string;
  other_rate: string;
  your_deduction: string;
  other_deduction: string;
  difference: string;
};

export type CalculatorResult = {
  tax_year: string;
  /** Set when the calculator refuses; `message` then says why, and every figure is null. */
  blocked_reason: "no_income" | "profit_over_limit" | null;
  message: string | null;
  incomes: IncomeLine[];
  taxable_income: string | null;
  /** Salary as a percentage of taxable income, e.g. "69.06". */
  salary_share: string | null;
  table: "salaried" | "non_salaried" | null;
  slab_tax: string | null;
  surcharge: string | null;
  dividend_tax: string | null;
  profit_tax: string | null;
  total_tax: string | null;
  /** Total tax as a percentage of total income, e.g. "23.7". */
  effective_rate: string | null;
  /** What an employer deducts each month on the salary alone (s.149), and what is left. */
  monthly: { salary_tax: string; take_home: string } | null;
  /** Can be negative: a bonus that lifts salary over 75% lowers the tax (the salaried table). */
  bonus_impact: string | null;
  filer_comparison: FilerLine[];
  /** The profile's ATL status the comparison used. */
  on_atl: boolean;
  steps: TaxStep[];
  not_covered: string[];
  label: string;
};

export const calculateTax = (input: CalculatorInput) =>
  apiFetch<CalculatorResult>("/api/tax/calculator", {
    method: "POST",
    body: input,
  });
