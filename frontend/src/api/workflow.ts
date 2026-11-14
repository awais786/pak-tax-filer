// The guided run (feature 007), per specs/007-agentic-workflow/contracts/workflow-api.md.
// Figures arrive as decimal strings and are only displayed (constitution, Principle I).

import { apiFetch } from "./client";
import type { TaxResult } from "./tax";

export type Step =
  "document" | "validate" | "research" | "gate" | "result" | "done";

export type Passage = {
  id: string;
  source: string;
  kind: "law" | "guidance";
  location: string;
  page: number;
  text: string;
};

export type Issue = {
  document_id: string;
  certificate: string;
  field: string;
  reason: string;
};

export type Run = {
  step: Step;
  tax_year: string;
  fingerprint: string | null;
  document: { message: string; missing: string[]; fallback: boolean } | null;
  validation: { message: string; issues: Issue[]; fallback: boolean } | null;
  research: { note: string; passages: Passage[]; fallback: boolean } | null;
  gate: {
    figures: {
      taxable_salary: string;
      tax_deducted: string;
      gross_profit: string;
      tax_withheld: string;
    };
    on_atl: boolean;
  } | null;
  approved_at: string | null;
  done_at: string | null;
  /** Steps 1-3 re-ran because the inputs changed after an approval (which they cleared). */
  inputs_changed: boolean;
};

export const getRun = () => apiFetch<Run>("/api/workflow");
export const startRun = () =>
  apiFetch<Run>("/api/workflow/start", { method: "POST" });

/** 004's result for the run (exactly the Tax page's body) plus the research passages. */
export type WorkflowResult = TaxResult & { passages: Passage[] };

export const approveRun = (fingerprint: string) =>
  apiFetch<Run>("/api/workflow/approve", {
    method: "POST",
    body: { fingerprint },
  });
export const backRun = () =>
  apiFetch<Run>("/api/workflow/back", { method: "POST" });
export const getResult = () => apiFetch<WorkflowResult>("/api/workflow/result");
export const markDone = () =>
  apiFetch<Run>("/api/workflow/done", { method: "POST" });

/** The guided run's approved result as a PDF (feature 008): a download address. */
export const WORKFLOW_PDF_URL = "/api/workflow/result/pdf";
