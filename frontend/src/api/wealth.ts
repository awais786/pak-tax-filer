// The wealth statement (feature 005), per specs/005-wealth-statement/contracts/wealth-api.md.
// Money travels as decimal strings of whole rupees and is only displayed, never calculated
// with (constitution, Principle I): the reconciliation is the backend's.

import { apiFetch } from "./client";

export type AssetRow = {
  category: string;
  description: string;
  amount: string;
};
export type LiabilityRow = {
  description: string;
  creditor: string | null;
  amount: string;
};

/** What the user enters; sent whole on every save. */
export type StatementIn = {
  previous_net_assets: string | null;
  assets: AssetRow[];
  liabilities: LiabilityRow[];
  other_exempt_income: string;
  foreign_remittance: string;
  inheritance: string;
  gifts_received: string;
  family_contribution: string;
  gifts_given: string;
  expenses: Record<string, string>;
};

export type StatementOut = StatementIn & { saved_at: string | null };

export type AutoFilledLine = {
  line: string | null;
  label: string;
  amount: string;
  certificates: string[];
  provisional: boolean;
};

export type WealthStep = {
  description: string;
  form_line: string;
  result: string;
};

export type NotReadyReason =
  | "needs_previous_net_assets"
  | "no_confirmed_salary_certificate"
  | "profit_over_limit"
  | "gross_below_taxable";
export type Direction =
  "reconciled" | "inflows_exceed_growth" | "growth_exceeds_inflows";

export type WealthResult = {
  not_ready_reason: NotReadyReason | null;
  message: string | null;
  net_assets: string | null;
  increase: string | null;
  inflows: string | null;
  outflows: string | null;
  unreconciled: string | null;
  direction: Direction | null;
  where_to_look: string[];
  steps: WealthStep[];
};

export type Wealth = {
  tax_year: string;
  statement: StatementOut;
  auto_filled: AutoFilledLine[];
  certificates_changed: boolean;
  result: WealthResult;
  label: string;
};

const path = (taxYear: string) => `/api/wealth/${encodeURIComponent(taxYear)}`;

export const getWealth = (taxYear: string) => apiFetch<Wealth>(path(taxYear));

export const saveWealth = (taxYear: string, statement: StatementIn) =>
  apiFetch<Wealth>(path(taxYear), { method: "PUT", body: statement });

/** The checked AI summary, on its own so the statement never waits for it (feature 001, US6). */
export const getWealthSummary = (taxYear: string) =>
  apiFetch<{ summary: string | null }>(`${path(taxYear)}/summary`);

/** IRIS asset categories (005 research R4), in the IRIS order. */
export const ASSET_CATEGORIES: [string, string][] = [
  ["immovable_property", "Immovable property"],
  ["investments", "Investments (stocks, bonds, etc.)"],
  ["advances_receivables", "Advances, prepayments and receivables"],
  ["cash_in_hand", "Cash in hand"],
  ["bank_account", "Bank account"],
  ["equipment", "Equipment"],
  ["animals", "Animals"],
  ["motor_vehicle", "Motor vehicle"],
  ["precious_possession", "Precious possessions (e.g. jewellery)"],
  ["household_effects", "Household effects"],
  ["personal_items", "Personal items"],
  ["assets_in_others_names", "Assets held in others' names"],
  ["other_asset", "Any other asset"],
];

/** IRIS personal-expense categories (005 research R3); their total is line 7089. */
export const EXPENSE_CATEGORIES: [string, string][] = [
  ["rent", "Rent"],
  ["rates_taxes", "Rates, taxes, charges, cess"],
  ["vehicle", "Vehicle running and maintenance"],
  ["electricity", "Electricity"],
  ["water", "Water"],
  ["gas", "Gas"],
  ["telephone", "Telephone"],
  ["asset_insurance", "Asset insurance / security"],
  ["medical", "Medical"],
  ["educational", "Educational"],
  ["club", "Club"],
  ["functions", "Functions / gatherings"],
  ["donations_zakat", "Donations, zakat, annuity"],
  ["other_household", "Other personal / household expenses"],
  ["foreign_travel", "Foreign travelling"],
  ["local_travel", "Local travelling"],
];

/** The wealth statement as a PDF (feature 008): a download address, not a fetch. */
export const wealthPdfUrl = (taxYear: string) =>
  `/api/wealth/${encodeURIComponent(taxYear)}/pdf`;
