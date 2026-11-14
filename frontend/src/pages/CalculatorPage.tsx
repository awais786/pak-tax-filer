import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { calculateTax } from "../api/calculator";
import type {
  CalculatorInput,
  CalculatorResult,
  FilerLine,
  IncomeLine,
} from "../api/calculator";
import { ApiError } from "../api/client";
import { rupees } from "../api/tax";
import { MoneyInput } from "../components/MoneyInput";
import { useProfile } from "../profile/ProfileContext";

// The simple tax calculator (feature 010, tasks T014, T017, T020), per
// specs/010-income-tax-engine/contracts/calculator-api.md. The user types amounts; every figure
// comes from the backend as a decimal string and is only displayed (Principle I). Nothing is
// saved. Tax year and ATL status come from the profile, so the form doesn't ask for them.

type Field = keyof CalculatorInput;

const FIELDS: [Field, string][] = [
  ["salary_monthly", "Salary per month"],
  ["bonus", "Bonus for the year"],
  ["rent_monthly", "Rent per month"],
  ["dividends", "Dividends for the year"],
  ["bank_profit", "Bank profit for the year"],
];

const SOURCES: Record<IncomeLine["source"], string> = {
  salary: "Salary",
  bonus: "Bonus",
  rent: "Rent",
  dividends: "Dividends",
  bank_profit: "Bank profit",
};

const TREATMENTS: Record<IncomeLine["treatment"], string> = {
  slab: "taxed in the slabs",
  final: "a final tax",
  separate: "taxed separately",
};

/** "Salary per month: must be …" from the server's "salary_monthly: must be …". */
function withLabels(message: string): string {
  return FIELDS.reduce(
    (text, [field, label]) => text.replaceAll(`${field}:`, `${label}:`),
    message,
  );
}

export function CalculatorPage() {
  const { profile } = useProfile();
  const [amounts, setAmounts] = useState<CalculatorInput>({});
  const [result, setResult] = useState<CalculatorResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    // Only what was typed is sent; an empty field counts as zero on the server.
    const typed: CalculatorInput = {};
    for (const [field] of FIELDS) {
      const value = (amounts[field] ?? "").trim();
      if (value !== "") {
        typed[field] = value;
      }
    }
    try {
      setResult(await calculateTax(typed));
    } catch (failure) {
      setResult(null);
      setError(
        failure instanceof ApiError && failure.status === 422
          ? withLabels(failure.message)
          : "The calculator couldn't answer. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const change = (field: Field, value: string) => {
    setAmounts((current) => ({ ...current, [field]: value }));
    // The shown result no longer matches the amounts: never leave stale figures up.
    setResult(null);
  };

  return (
    <main>
      <h1>Tax calculator for {profile?.tax_year ?? ""}</h1>
      <p className="lede">
        Type your incomes to see an idea of your tax. Nothing you type is saved.
      </p>
      <form onSubmit={submit} className="plain" noValidate>
        <fieldset className="entry-row">
          <legend className="visually-hidden">Your incomes</legend>
          {FIELDS.map(([field, label]) => (
            <label key={field}>
              {label}
              <MoneyInput
                inputMode="decimal"
                value={amounts[field] ?? ""}
                onChange={(e) => change(field, e.target.value)}
              />
            </label>
          ))}
        </fieldset>
        <div className="save-bar">
          <button
            type="submit"
            disabled={busy}
            aria-describedby={error !== null ? "calculator-error" : undefined}
          >
            {busy ? "Calculating…" : "Calculate"}
          </button>
          {error !== null && (
            <p id="calculator-error" role="alert">
              {error}
            </p>
          )}
          <p role="status">{busy ? "Calculating…" : ""}</p>
        </div>
      </form>
      {result !== null && <Result result={result} />}
    </main>
  );
}

function Result({ result }: { result: CalculatorResult }) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  // A new result appears below the form: take keyboard and screen-reader users to it.
  useEffect(() => {
    heading.current?.focus();
  }, [result]);
  return (
    <section aria-labelledby="calculator-result-heading">
      <h2 id="calculator-result-heading" tabIndex={-1} ref={heading}>
        Your tax
      </h2>
      <p className="notice">{result.label}</p>
      {result.blocked_reason !== null ? (
        <p className="panel">{result.message}</p>
      ) : (
        <Figures result={result} />
      )}
      <section aria-labelledby="not-covered-heading" className="panel">
        <h3 id="not-covered-heading">Not covered by the calculator</h3>
        <ul>
          {result.not_covered.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </section>
  );
}

function Figures({ result }: { result: CalculatorResult }) {
  return (
    <>
      {result.total_tax !== null && (
        <p className="headline">{rupees(result.total_tax)}</p>
      )}
      {result.effective_rate !== null && (
        <p className="hint">
          Total tax for the year: {result.effective_rate}% of your income.
        </p>
      )}
      {result.table !== null && result.taxable_income !== null ? (
        <p>
          Salary is {result.salary_share}% of your taxable income of{" "}
          <span>{rupees(result.taxable_income)}</span>, so the{" "}
          {result.table === "salaried" ? "salaried" : "non-salaried"} table
          applies. The steps below give the rule.
        </p>
      ) : (
        <p>No slab tax: dividends and bank profit are taxed on their own.</p>
      )}
      <dl className="figures">
        {result.incomes.map((line) => (
          <div key={line.source}>
            <dt>
              {SOURCES[line.source]} ({TREATMENTS[line.treatment]})
            </dt>
            <dd>
              {rupees(line.yearly_amount)}
              {/* Only rent is taxed on less than it is (the repairs allowance). */}
              {line.source === "rent" && (
                <>
                  , taxed on <span>{rupees(line.taxable_amount)}</span>
                </>
              )}
            </dd>
          </div>
        ))}
        {result.table !== null && (
          <TaxLine label="Tax on taxable income" amount={result.slab_tax} />
        )}
        <TaxLine label="Surcharge" amount={result.surcharge} hideZero />
        <TaxLine
          label="Tax on dividends"
          amount={result.dividend_tax}
          hideZero
        />
        <TaxLine
          label="Tax on bank profit"
          amount={result.profit_tax}
          hideZero
        />
        <TaxLine label="Total tax" amount={result.total_tax} />
      </dl>
      {result.monthly !== null && (
        <section aria-labelledby="monthly-heading" className="panel">
          <h3 id="monthly-heading">Each month</h3>
          <dl className="figures">
            <div>
              <dt>Your employer deducts, on the salary alone</dt>
              <dd>{rupees(result.monthly.salary_tax)}</dd>
            </div>
            <div>
              <dt>Take-home pay</dt>
              <dd>{rupees(result.monthly.take_home)}</dd>
            </div>
          </dl>
          <p className="hint">
            Any other tax on your incomes is settled with your return.
          </p>
        </section>
      )}
      {result.bonus_impact !== null && (
        <BonusWords impact={result.bonus_impact} />
      )}
      {result.filer_comparison.length > 0 && (
        <section aria-labelledby="filer-heading" className="panel">
          <h3 id="filer-heading">Filer or not: tax deducted at source</h3>
          <ul>
            {result.filer_comparison.map((line) => (
              <li key={line.source}>
                <FilerWords line={line} onAtl={result.on_atl} />
              </li>
            ))}
          </ul>
          <p className="hint">
            The tax itself is the same either way; only the amount deducted when
            you are paid changes. Whether extra tax deducted can be reclaimed
            isn't something this calculator says.
          </p>
        </section>
      )}
      <h3 id="calculator-steps-heading">How it was worked out</h3>
      <ol
        aria-labelledby="calculator-steps-heading"
        className="ledger"
        role="list"
      >
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

/** A tax line; `hideZero` leaves out a line with nothing due (the string "0", not a sum). */
function TaxLine({
  label,
  amount,
  hideZero = false,
}: {
  label: string;
  amount: string | null;
  hideZero?: boolean;
}) {
  if (amount === null || (hideZero && /^0+(\.0*)?$/.test(amount))) {
    return null;
  }
  return (
    <div>
      <dt>{label}</dt>
      <dd>{rupees(amount)}</dd>
    </div>
  );
}

/** The bonus impact in words; a leading "-" (from the server) means it lowers the tax. */
function BonusWords({ impact }: { impact: string }) {
  if (impact.startsWith("-")) {
    return (
      <p>
        Your bonus lowers your tax by {rupees(impact)}: it lifts your salary
        over 75% of your taxable income, so the salaried table applies.
      </p>
    );
  }
  return <p>Your bonus adds {rupees(impact)} to your tax.</p>;
}

function FilerWords({ line, onAtl }: { line: FilerLine; onAtl: boolean }) {
  const you = onAtl ? "on the ATL" : "not on the ATL";
  const other = onAtl ? "not on the ATL" : "on the ATL";
  return (
    <>
      {SOURCES[line.source]}: {rupees(line.your_deduction)} deducted at{" "}
      {line.your_rate}% for you ({you}); {rupees(line.other_deduction)} at{" "}
      {line.other_rate}% for someone {other}, a difference of{" "}
      {rupees(line.difference)}.
    </>
  );
}
