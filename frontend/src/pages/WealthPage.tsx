import { useEffect, useRef, useState } from "react";
import type { FormEvent, RefObject } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { rupees } from "../api/tax";
import {
  ASSET_CATEGORIES,
  EXPENSE_CATEGORIES,
  getWealth,
  getWealthSummary,
  saveWealth,
  wealthPdfUrl,
} from "../api/wealth";
import type {
  AutoFilledLine,
  StatementIn,
  Wealth,
  WealthResult,
} from "../api/wealth";
import { DownloadPdfButton } from "../components/DownloadPdfButton";
import { MoneyInput } from "../components/MoneyInput";
import { SummaryPanel } from "../components/SummaryPanel";
import { useProfile } from "../profile/ProfileContext";

// The wealth statement for the profile's tax year (feature 005, tasks T011, T017, T023). The
// user enters what they own, owe and spent; the backend fills in the certificate lines and
// reconciles. This page only displays its figures (constitution, Principles I and IV).

type Asset = {
  key: number;
  category: string;
  description: string;
  amount: string;
};
type Liability = {
  key: number;
  description: string;
  creditor: string;
  amount: string;
};
type MoneyField =
  | "other_exempt_income"
  | "foreign_remittance"
  | "inheritance"
  | "gifts_received"
  | "family_contribution"
  | "gifts_given";
type Form = Pick<StatementIn, MoneyField | "expenses"> & {
  previous_net_assets: string;
  assets: Asset[];
  liabilities: Liability[];
};

const MONEY_FIELDS: [MoneyField, string][] = [
  ["other_exempt_income", "Other exempt income"],
  ["foreign_remittance", "Foreign remittance"],
  ["inheritance", "Inheritance"],
  ["gifts_received", "Gifts received"],
  ["family_contribution", "Family members' contribution to expenses"],
  ["gifts_given", "Gifts given"],
];

let nextKey = 0;
const key = () => ++nextKey;

/** "30 June 2026" (this statement's date) and "30 June 2025" (last year's) for "2025-26". */
function statementDates(taxYear: string) {
  const end = Number(taxYear.slice(0, 4)) + 1;
  return { now: `30 June ${end}`, before: `30 June ${end - 1}` };
}

function toForm(statement: Wealth["statement"]): Form {
  return {
    previous_net_assets: statement.previous_net_assets ?? "",
    other_exempt_income: statement.other_exempt_income,
    foreign_remittance: statement.foreign_remittance,
    inheritance: statement.inheritance,
    gifts_received: statement.gifts_received,
    family_contribution: statement.family_contribution,
    gifts_given: statement.gifts_given,
    expenses: statement.expenses,
    assets: statement.assets.map((a) => ({ key: key(), ...a })),
    liabilities: statement.liabilities.map((l) => ({
      key: key(),
      ...l,
      creditor: l.creditor ?? "",
    })),
  };
}

/** The statement as the API takes it: empty amounts are zero, an empty previous figure is
 * "not entered", empty expense categories are left out. The server checks every rule. */
function toStatement(form: Form): StatementIn {
  const zero = (value: string) => value.trim() || "0";
  return {
    previous_net_assets: form.previous_net_assets.trim() || null,
    assets: form.assets.map(({ category, description, amount }) => ({
      category,
      description: description.trim(),
      amount: zero(amount),
    })),
    liabilities: form.liabilities.map(({ description, creditor, amount }) => ({
      description: description.trim(),
      creditor: creditor.trim() || null,
      amount: zero(amount),
    })),
    other_exempt_income: zero(form.other_exempt_income),
    foreign_remittance: zero(form.foreign_remittance),
    inheritance: zero(form.inheritance),
    gifts_received: zero(form.gifts_received),
    family_contribution: zero(form.family_contribution),
    gifts_given: zero(form.gifts_given),
    expenses: Object.fromEntries(
      Object.entries(form.expenses)
        .map(([category, value]) => [category, value.trim()])
        .filter(([, value]) => value !== ""),
    ),
  };
}

const message = (caught: unknown, fallback: string) =>
  caught instanceof ApiError ? caught.message : fallback;

export function WealthPage() {
  const { profile } = useProfile();
  // RequireProfile renders this page only once the profile has loaded.
  const taxYear = profile?.tax_year ?? "";
  const [wealth, setWealth] = useState<Wealth | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  // Changes not yet saved: the PDF is of the saved statement, so it waits for them (008).
  const [edited, setEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveAttempts, setSaveAttempts] = useState(0);
  // Each statement shown (loaded or saved) gets a new number, so its summary is asked for anew.
  const [version, setVersion] = useState(0);
  const [shownYear, setShownYear] = useState(taxYear);
  const saveButton = useRef<HTMLButtonElement | null>(null);
  // The year a save was sent for; a reply for another year is ignored.
  const currentYear = useRef(taxYear);

  useEffect(() => {
    currentYear.current = taxYear;
  }, [taxYear]);

  // After a save, focus goes back to Save (disabling it while saving dropped focus to the
  // page's top): keyboard and screen-reader users stay where they were.
  useEffect(() => {
    if (saveAttempts > 0 && !saving) {
      saveButton.current?.focus();
    }
  }, [saveAttempts, saving]);

  // A different year: forget the previous one (React's reset-on-change pattern).
  if (taxYear !== shownYear) {
    setShownYear(taxYear);
    setWealth(null);
    setForm(null);
    setLoadError(null);
    setSaveError(null);
    setSaved(false);
    setEdited(false);
  }

  useEffect(() => {
    let current = true;
    if (taxYear === "") {
      return;
    }
    getWealth(taxYear)
      .then((loaded) => {
        if (current) {
          setWealth(loaded);
          setForm(toForm(loaded.statement));
          setEdited(false);
          setVersion((n) => n + 1);
        }
      })
      .catch((caught: unknown) => {
        if (current) {
          setLoadError(
            message(caught, "Couldn't load your wealth statement. Try again."),
          );
        }
      });
    return () => {
      current = false;
    };
  }, [taxYear]);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form === null) {
      return;
    }
    const year = taxYear;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const result = await saveWealth(year, toStatement(form));
      if (currentYear.current !== year) {
        return;
      }
      setWealth(result);
      setForm(toForm(result.statement));
      setVersion((n) => n + 1);
      setSaved(true);
      setEdited(false);
    } catch (caught) {
      setSaveError(message(caught, "Couldn't save. Try again."));
    } finally {
      setSaving(false);
      setSaveAttempts((count) => count + 1);
    }
  }

  const update = (changes: Partial<Form>) => {
    setSaved(false);
    setEdited(true);
    setForm((current) => (current ? { ...current, ...changes } : current));
  };
  const dates = statementDates(taxYear);

  return (
    <main>
      <h1>Wealth statement for {taxYear}</h1>
      {loadError !== null && <p role="alert">{loadError}</p>}
      {wealth === null || form === null ? (
        loadError === null && (
          <>
            <p role="status">Loading…</p>
            {/* The shape of the statement while it loads (task T062). */}
            <div aria-hidden="true">
              <div className="skeleton skeleton-line" />
              <div className="skeleton skeleton-card" />
              <div className="skeleton skeleton-card" />
            </div>
          </>
        )
      ) : (
        <>
          {wealth.certificates_changed && (
            <p className="notice">
              Your confirmed certificates changed since you last saved. Check
              the result below and save again.
            </p>
          )}
          <SectionBar />
          {/* No autofill: these are amounts, not personal details. */}
          <form onSubmit={handleSave} autoComplete="off">
            {/* Disabled while saving: the saved statement then replaces the form, so
                anything typed meanwhile would be lost. */}
            <fieldset
              disabled={saving}
              aria-label="Your statement"
              className="plain"
            >
              <Assets form={form} update={update} asOn={dates.now} />
              <Liabilities form={form} update={update} />
              <MoneyInAndOut
                form={form}
                update={update}
                autoFilled={wealth.auto_filled}
                previousDate={dates.before}
              />
            </fieldset>
            <div className="save-bar">
              <button
                type="submit"
                ref={saveButton}
                disabled={saving}
                aria-describedby={
                  saveError !== null ? "wealth-save-error" : undefined
                }
              >
                {saving ? "Saving…" : "Save"}
              </button>
              {saveError !== null && (
                <p id="wealth-save-error" role="alert">
                  {saveError}
                </p>
              )}
              {/* One live region, always present, so "Saved." is announced when it appears. */}
              <p role="status">{saved ? "Saved." : ""}</p>
            </div>
          </form>
          <Result
            result={wealth.result}
            label={wealth.label}
            taxYear={taxYear}
            version={version}
            edited={edited}
          />
        </>
      )}
    </main>
  );
}

type FormProps = { form: Form; update: (changes: Partial<Form>) => void };

/** Removing a row moves focus to the "Add" button, not to the page's top. */
function useFocusAfterRemove(): [
  RefObject<HTMLButtonElement | null>,
  () => void,
] {
  const ref = useRef<HTMLButtonElement | null>(null);
  return [ref, () => ref.current?.focus()];
}

function Assets({ form, update, asOn }: FormProps & { asOn: string }) {
  const [addButton, focusAdd] = useFocusAfterRemove();
  const change = (k: number, changes: Partial<Asset>) =>
    update({
      assets: form.assets.map((a) => (a.key === k ? { ...a, ...changes } : a)),
    });
  return (
    <section aria-labelledby="own-heading" className="statement-section">
      <h2 id="own-heading">What I own</h2>
      <p className="lede">Each asset at its cost, as on {asOn}.</p>
      {form.assets.map((asset, index) => (
        <fieldset key={asset.key} className="entry-row">
          <legend>Asset {index + 1}</legend>
          <label>
            Category
            <select
              value={asset.category}
              onChange={(e) => change(asset.key, { category: e.target.value })}
            >
              {ASSET_CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Description
            <input
              value={asset.description}
              maxLength={200}
              required
              onChange={(e) =>
                change(asset.key, { description: e.target.value })
              }
            />
          </label>
          <label>
            Amount
            <MoneyInput
              inputMode="numeric"
              value={asset.amount}
              onChange={(e) => change(asset.key, { amount: e.target.value })}
            />
          </label>
          <button
            type="button"
            onClick={() => {
              update({
                assets: form.assets.filter((a) => a.key !== asset.key),
              });
              focusAdd();
            }}
          >
            {/* "Remove" on screen; the full name says which row. */}
            Remove <span className="visually-hidden">asset {index + 1}</span>
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        ref={addButton}
        onClick={() =>
          update({
            assets: [
              ...form.assets,
              {
                key: key(),
                category: "bank_account",
                description: "",
                amount: "",
              },
            ],
          })
        }
      >
        Add an asset
      </button>
    </section>
  );
}

function Liabilities({ form, update }: FormProps) {
  const [addButton, focusAdd] = useFocusAfterRemove();
  const change = (k: number, changes: Partial<Liability>) =>
    update({
      liabilities: form.liabilities.map((l) =>
        l.key === k ? { ...l, ...changes } : l,
      ),
    });
  return (
    <section aria-labelledby="owe-heading" className="statement-section">
      <h2 id="owe-heading">What I owe</h2>
      {form.liabilities.map((row, index) => (
        <fieldset key={row.key} className="entry-row liability">
          <legend>Liability {index + 1}</legend>
          <label>
            Description
            <input
              value={row.description}
              maxLength={200}
              required
              onChange={(e) => change(row.key, { description: e.target.value })}
            />
          </label>
          <label>
            Creditor
            <input
              value={row.creditor}
              maxLength={200}
              onChange={(e) => change(row.key, { creditor: e.target.value })}
            />
          </label>
          <label>
            Amount
            <MoneyInput
              inputMode="numeric"
              value={row.amount}
              onChange={(e) => change(row.key, { amount: e.target.value })}
            />
          </label>
          <button
            type="button"
            onClick={() => {
              update({
                liabilities: form.liabilities.filter((l) => l.key !== row.key),
              });
              focusAdd();
            }}
          >
            Remove{" "}
            <span className="visually-hidden">liability {index + 1}</span>
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        ref={addButton}
        onClick={() =>
          update({
            liabilities: [
              ...form.liabilities,
              { key: key(), description: "", creditor: "", amount: "" },
            ],
          })
        }
      >
        Add a liability
      </button>
    </section>
  );
}

function MoneyInAndOut({
  form,
  update,
  autoFilled,
  previousDate,
}: FormProps & { autoFilled: AutoFilledLine[]; previousDate: string }) {
  const filledExpenses = Object.values(form.expenses).filter(
    (value) => value.trim() !== "",
  ).length;
  return (
    <section aria-labelledby="money-heading" className="statement-section">
      <h2 id="money-heading">Money in and out</h2>
      <h3 id="certificates-heading">From your certificates</h3>
      <ul
        aria-labelledby="certificates-heading"
        className="auto-filled"
        role="list"
      >
        {autoFilled.map((line) => (
          <li key={line.label}>
            <strong>
              {line.label}
              {line.line ? ` (${line.line})` : ""}
            </strong>{" "}
            <span className="money">{rupees(line.amount)}</span>{" "}
            <small>
              {line.certificates.length
                ? `From: ${line.certificates.join(", ")}`
                : "No confirmed certificate"}
            </small>
            {line.provisional && <small> (provisional)</small>}
          </li>
        ))}
      </ul>
      <p>
        These come from your confirmed certificates and can't be changed here.
        To correct one, correct the certificate: delete it on{" "}
        <Link to="/documents">Documents</Link> and upload it again.
      </p>
      <label>
        Net assets on {previousDate} (from last year's statement)
        {/* No numeric keypad: this one may be negative, and phone keypads lack a minus. */}
        <MoneyInput
          aria-describedby="previous-hint"
          value={form.previous_net_assets}
          onChange={(e) => update({ previous_net_assets: e.target.value })}
        />
      </label>
      <p id="previous-hint" className="hint">
        May be negative, if you owed more than you owned.
      </p>
      <div className="money-grid">
        {MONEY_FIELDS.map(([field, label]) => (
          <label key={field}>
            {label}
            <MoneyInput
              inputMode="numeric"
              value={form[field]}
              onChange={(e) => update({ [field]: e.target.value })}
            />
          </label>
        ))}
      </div>
      {/* Foldable once filled in; open by default, as expenses count towards the
          reconciliation. The heading counts fields filled, never money (task T068). */}
      <details className="fold" open>
        <summary>
          Personal expenses ({filledExpenses} of {EXPENSE_CATEGORIES.length}{" "}
          filled)
        </summary>
        <div className="money-grid">
          {EXPENSE_CATEGORIES.map(([category, label]) => (
            <label key={category}>
              {label}
              <MoneyInput
                inputMode="numeric"
                value={form.expenses[category] ?? ""}
                onChange={(e) =>
                  update({
                    expenses: { ...form.expenses, [category]: e.target.value },
                  })
                }
              />
            </label>
          ))}
        </div>
      </details>
    </section>
  );
}

const SECTIONS = [
  ["own-heading", "What I own"],
  ["owe-heading", "What I owe"],
  ["money-heading", "Money in and out"],
  ["result-heading", "Result"],
];

/** Links to each part of a long page, so a phone user can jump instead of scrolling. */
function SectionBar() {
  return (
    <nav aria-label="Sections of the statement" className="section-bar">
      <ul>
        {SECTIONS.map(([id, text]) => (
          <li key={id}>
            <a href={`#${id}`}>{text}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

type ResultProps = {
  result: WealthResult;
  label: string;
  taxYear: string;
  /** Changes with every load and save, so the summary is asked for again. */
  version: number;
  /** The form has changes not yet saved (the PDF is of the saved statement). */
  edited: boolean;
};

function Result({ result, label, taxYear, version, edited }: ResultProps) {
  return (
    <section aria-labelledby="result-heading" className="result">
      <h2 id="result-heading">Result</h2>
      <p className="notice">{label}</p>
      <DownloadPdfButton
        url={wealthPdfUrl(taxYear)}
        disabledReason={
          result.not_ready_reason !== null
            ? "No PDF until your statement can be reconciled."
            : edited
              ? "Save your changes first: the PDF is of your saved statement."
              : null
        }
      />
      {result.message && <p className="result-message">{result.message}</p>}
      {result.not_ready_reason === null && (
        <>
          {result.where_to_look.length > 0 && (
            <>
              <h3 id="look-heading">Where to look</h3>
              <ul aria-labelledby="look-heading" className="panel">
                {result.where_to_look.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
          {/* Loaded on its own, and again after each save (a new `key`). */}
          <SummaryPanel
            key={version}
            fetchSummary={getWealthSummary}
            taxYear={taxYear}
            headingId="wealth-summary-heading"
            level={3}
          />
          <h3 id="wealth-breakdown-heading">How it was worked out</h3>
          <ol
            aria-labelledby="wealth-breakdown-heading"
            className="ledger"
            role="list"
          >
            {result.steps.map((step, index) => (
              <li key={`${index}-${step.form_line}`}>
                {step.description}
                <small>Form line {step.form_line}</small>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
