import { Link } from "react-router";
import { balanceWords, getTaxSummary, rupees } from "../api/tax";
import type { TaxResult } from "../api/tax";
import { DownloadPdfButton } from "./DownloadPdfButton";
import { SummaryPanel } from "./SummaryPanel";

// A tax result as 004's engine returns it (feature 004; moved here for 007's guided run, task
// T016): the practitioner label, the blocked message or both sides' figures, the checked
// summary and the cited breakdown. Figures are shown as the API gives them; nothing is
// calculated here (Principle I).

/** Where to go to fix a refusal the user can fix themselves. */
const FIX_LINKS: Record<string, { to: string; text: string }> = {
  needs_atl_answer: { to: "/profile", text: "Go to your profile" },
  no_confirmed_salary_certificate: {
    to: "/documents",
    text: "Go to documents",
  },
};

export function TaxResultView({
  result,
  pdfUrl,
}: {
  result: TaxResult;
  /** Where this result's PDF downloads from (feature 008). */
  pdfUrl: string;
}) {
  const fix = FIX_LINKS[result.blocked_reason ?? ""];
  return (
    <>
      <p className="notice">{result.label}</p>
      <DownloadPdfButton
        url={pdfUrl}
        disabledReason={
          result.blocked_reason === null
            ? null
            : "No PDF until this result can be calculated."
        }
      />
      {result.blocked_reason !== null ? (
        <p className="panel">
          {result.message}
          {fix && (
            <>
              {" "}
              <Link to={fix.to}>{fix.text}</Link>
            </>
          )}
        </p>
      ) : (
        <Figures result={result} />
      )}
    </>
  );
}

/** One figure as the API gave it; left out when the API sent none (never shown as Rs 0). */
function Row({
  term,
  amount,
  less = false,
}: {
  term: string;
  amount: string | null;
  /** Taken off: shown with a minus sign, as the API's figure (nothing is calculated here). */
  less?: boolean;
}) {
  if (amount === null) {
    return null;
  }
  return (
    <>
      <dt>{term}</dt>
      <dd>{less ? `− ${rupees(amount)}` : rupees(amount)}</dd>
    </>
  );
}

/** A side's answer in large type, with what it is beneath; nothing if the API sent none. */
function Headline({ text, caption }: { text: string | null; caption: string }) {
  if (text === null) {
    return null;
  }
  return (
    <>
      <p className="headline">{text}</p>
      <p className="hint">{caption}</p>
    </>
  );
}

const words = (balance: string | null, overpaid: string) =>
  balance === null ? null : balanceWords(balance, overpaid);

function Figures({ result }: { result: TaxResult }) {
  return (
    <>
      {/* Shown separately: whether one side can be set off against the other is still
          a question for the lead, so there is no combined total (spec clarification). Each
          side's balance is its headline, above the parts it is made of (001, task T054). */}
      <div className="headline-pair">
        <section aria-labelledby="salary-heading" className="panel">
          <h2 id="salary-heading">Salary</h2>
          <Headline
            text={words(result.salary_balance, "over-deducted")}
            caption="After tax deducted by employers"
          />
          <dl className="figures">
            <Row term="Salary tax" amount={result.salary_tax} />
            <Row term="Surcharge" amount={result.surcharge} />
            <Row
              term="Less tax deducted by employers"
              amount={result.salary_credit}
              less
            />
          </dl>
        </section>
        <section aria-labelledby="profit-heading" className="panel">
          <h2 id="profit-heading">Bank profit</h2>
          <Headline
            text={words(result.profit_balance, "over-withheld")}
            caption="After tax withheld by banks"
          />
          <dl className="figures">
            <Row term="Tax on bank profit" amount={result.profit_tax} />
            <Row
              term="Less tax withheld by banks"
              amount={result.profit_credit}
              less
            />
          </dl>
          {result.non_atl_extra_withheld !== null && (
            <p className="notice">
              <strong>Not on the ATL:</strong>{" "}
              <span>
                {`${rupees(result.non_atl_extra_withheld)} extra tax withheld; whether it can be reclaimed needs confirmation`}
              </span>
            </p>
          )}
        </section>
      </div>
      {/* Loaded on its own, so the figures above never wait for the AI. */}
      <SummaryPanel
        key={result.tax_year}
        fetchSummary={getTaxSummary}
        taxYear={result.tax_year}
        headingId="summary-heading"
      />
      <h2 id="breakdown-heading">How it was worked out</h2>
      <ol aria-labelledby="breakdown-heading" className="ledger" role="list">
        {result.steps.map((step, index) => (
          <li key={`${index}-${step.description}`}>
            {step.description}
            <small>Source: {step.rule_location}</small>
          </li>
        ))}
      </ol>
    </>
  );
}
