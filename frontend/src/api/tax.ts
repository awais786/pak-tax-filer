// The tax result (feature 004), per specs/004-tax-engine/contracts/tax-api.md. Money arrives as
// decimal strings and is only displayed, never calculated with (constitution, Principle I).

import { apiFetch } from "./client";

export type TaxStep = {
  description: string;
  rule_location: string;
  result: string;
};

export type TaxResult = {
  tax_year: string;
  /** Set when the calculation is refused; `message` then says what to do. */
  blocked_reason: string | null;
  message: string | null;
  salary_tax: string | null;
  surcharge: string | null;
  profit_tax: string | null;
  /** Positive: payable; negative: over-deducted. */
  salary_balance: string | null;
  /** Positive: payable; negative: over-withheld. */
  profit_balance: string | null;
  /** Non-ATL users only: withholding above the profit tax, "to be confirmed". */
  non_atl_extra_withheld: string | null;
  /** Tax deducted by employers (what the salary side was reduced by). */
  salary_credit: string | null;
  /** Tax withheld by banks, as counted against the profit tax. */
  profit_credit: string | null;
  steps: TaxStep[];
  label: string;
};

export const getTax = (taxYear: string) =>
  apiFetch<TaxResult>(`/api/tax/${encodeURIComponent(taxYear)}`);

/** The checked AI summary, on its own so the figures never wait for it (feature 001, US6). */
export const getTaxSummary = (taxYear: string) =>
  apiFetch<{ summary: string | null }>(
    `/api/tax/${encodeURIComponent(taxYear)}/summary`,
  );

/**
 * "Rs 1,234,567.5" from "1234567.5": digit grouping on the string itself, so the value is
 * never turned into a float. A leading "-" is dropped; callers say which way it goes.
 */
export function rupees(amount: string): string {
  const [whole, fraction] = amount.replace(/^-/, "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `Rs ${grouped}${fraction === undefined ? "" : `.${fraction}`}`;
}

/** "Rs 12,000 payable", "Rs 4,000 over-withheld" or "Nothing to pay". */
export function balanceWords(balance: string, overpaid: string): string {
  if (/^-?0*(\.0*)?$/.test(balance)) {
    return "Nothing to pay";
  }
  return `${rupees(balance)} ${balance.startsWith("-") ? overpaid : "payable"}`;
}

// Feature 001, task T066: amounts repeated with digit grouping beneath their fields.

/** A plain amount as typed or stored: digits, an optional "-" and decimals. */
const PLAIN_AMOUNT = /^-?\d+(\.\d+)?$/;

/**
 * "Rs 7,635,000.00" for "7635000.00", or null when there's nothing worth repeating: not a plain
 * amount, or too short to need grouping. String formatting only, never arithmetic (Principle I).
 */
export function groupedAmount(value: unknown): string | null {
  const text = typeof value === "string" ? value.trim() : "";
  if (
    !PLAIN_AMOUNT.test(text) ||
    text.replace(/^-/, "").split(".")[0].length < 4
  ) {
    return null;
  }
  return `${text.startsWith("-") ? "−" : ""}${rupees(text)}`;
}

/** The tax result as a PDF (feature 008): a download address, not a fetch. */
export const taxPdfUrl = (taxYear: string) =>
  `/api/tax/${encodeURIComponent(taxYear)}/pdf`;
