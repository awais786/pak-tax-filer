import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { rupees } from "../api/tax";
import {
  approveRun,
  backRun,
  getResult,
  getRun,
  markDone,
  startRun,
  WORKFLOW_PDF_URL,
} from "../api/workflow";
import type { Passage, Run, Step, WorkflowResult } from "../api/workflow";
import { TaxResultView } from "../components/TaxResultView";

// The guided run (feature 007, tasks T011, T016, T020): documents, figures and the law that
// applies, the approval gate, then the result. Every message and figure comes from the
// backend, which checked them and enforces the gate; the page computes nothing (Principle I)
// and shows which texts the app wrote without the AI.

/** Shown in turn while steps 1-3 run in one request (FR-019, research R10). */
const PROGRESS = [
  "Checking your documents…",
  "Checking the figures…",
  "Finding the law that applies…",
];
const PROGRESS_STEP_MS = 2000;
const PLAIN = "Written by the app (the AI wasn't used)";

/**
 * The indicator's labels. Steps 1-3 run in one request, so "Figures" and "Law" are never the
 * current step on their own; they show as done once the run is past them.
 */
const STEPS: { label: string; steps: Step[] }[] = [
  { label: "Documents", steps: ["document"] },
  { label: "Figures", steps: ["validate"] },
  { label: "Law", steps: ["research"] },
  { label: "Approve", steps: ["gate"] },
  { label: "Result", steps: ["result", "done"] },
];

/** Where focus goes after an action lands on each step (the result's heading waits for it). */
const FOCUS: Partial<Record<Step, string>> = {
  document: "documents-heading",
  gate: "gate-heading",
  done: "done-notice",
};

type Loaded =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "none" }
  | { kind: "run"; run: Run };

export function WorkflowPage() {
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  // After an action, focus follows the new content (keyboard and screen-reader users).
  const [focusNext, setFocusNext] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const mounted = useRef(true);

  /** Load (or reload) the run; a 404 means none was started. */
  const load = useCallback(async () => {
    try {
      const run = await getRun();
      if (mounted.current) setLoaded({ kind: "run", run });
    } catch (caught: unknown) {
      if (!mounted.current) return;
      if (caught instanceof ApiError && caught.status === 404) {
        setLoaded({ kind: "none" });
      } else {
        setError(message(caught));
        setLoaded((now) => (now.kind === "run" ? now : { kind: "failed" }));
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      window.clearInterval(timer.current);
    };
  }, [load]);

  const run = loaded.kind === "run" ? loaded.run : null;

  useEffect(() => {
    if (!focusNext || run === null) return;
    const target = FOCUS[run.step];
    if (target !== undefined) {
      document.getElementById(target)?.focus();
      setFocusNext(false);
    }
  }, [focusNext, run]);

  async function retry() {
    setError(null);
    setLoaded({ kind: "loading" });
    await load();
  }

  async function start() {
    if (progress !== null || busy) return;
    setError(null);
    setProgress(0);
    timer.current = window.setInterval(
      () =>
        setProgress((now) =>
          now === null ? null : Math.min(now + 1, PROGRESS.length - 1),
        ),
      PROGRESS_STEP_MS,
    );
    try {
      const started = await startRun();
      if (!mounted.current) return;
      setLoaded({ kind: "run", run: started });
      setFocusNext(true);
    } catch (caught: unknown) {
      if (mounted.current) setError(message(caught));
    } finally {
      window.clearInterval(timer.current);
      if (mounted.current) setProgress(null);
    }
  }

  /** A gate or result action; a refusal (409) reloads the run so the page shows the truth. */
  async function act(action: () => Promise<Run>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = await action();
      if (!mounted.current) return;
      setLoaded({ kind: "run", run: next });
      setFocusNext(true);
    } catch (caught: unknown) {
      if (!mounted.current) return;
      setError(message(caught));
      if (caught instanceof ApiError && caught.status === 409) await load();
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  const missing = (run?.document?.missing.length ?? 0) > 0;
  const canStart = loaded.kind === "none" || run?.step === "document";
  return (
    <main>
      <h1>Guided filing</h1>
      <p>
        PakTaxFiler checks your documents and figures, finds the parts of the
        tax law that apply to you, and then stops for you to approve before
        anything is calculated.
      </p>
      {run && <StepIndicator step={run.step} />}
      <p role="status">
        {progress !== null
          ? PROGRESS[progress]
          : loaded.kind === "loading" && "Loading your guided run…"}
      </p>
      {error !== null && <p role="alert">{error}</p>}
      {loaded.kind === "failed" && (
        <button type="button" onClick={retry}>
          Try again
        </button>
      )}
      {run && run.step !== "result" && run.step !== "done" && (
        <RunView run={run} />
      )}
      {run?.step === "gate" && run.fingerprint !== null && (
        <div className="actions">
          <button
            type="button"
            className="button-primary"
            aria-disabled={busy}
            onClick={() => act(() => approveRun(run.fingerprint!))}
          >
            Approve
          </button>
          <button
            type="button"
            aria-disabled={busy}
            onClick={() => act(backRun)}
          >
            Go back
          </button>
        </div>
      )}
      {run && (run.step === "result" || run.step === "done") && (
        <ResultView
          run={run}
          busy={busy}
          focusOnLoad={focusNext}
          onFocused={() => setFocusNext(false)}
          onDone={() => act(markDone)}
          onRefused={load}
        />
      )}
      {canStart && (
        <button
          type="button"
          // With a certificate missing, "Go to documents" is the main action.
          className={missing ? undefined : "button-primary"}
          aria-disabled={progress !== null}
          onClick={start}
        >
          {run ? "Start again" : "Start"}
        </button>
      )}
    </main>
  );
}

function message(caught: unknown): string {
  return caught instanceof ApiError
    ? caught.message
    : "Couldn't reach PakTaxFiler. Check your connection and try again.";
}

function StepIndicator({ step }: { step: Step }) {
  const current = STEPS.findIndex(({ steps }) => steps.includes(step));
  return (
    <ol className="run-steps" aria-label="Steps" role="list">
      {STEPS.map(({ label }, index) => (
        <li
          key={label}
          aria-current={index === current ? "step" : undefined}
          data-done={index < current || undefined}
        >
          {label}
          {index < current && <span className="visually-hidden"> (done)</span>}
        </li>
      ))}
    </ol>
  );
}

function RunView({ run }: { run: Run }) {
  return (
    <>
      {run.document && (
        <section className="panel" aria-labelledby="documents-heading">
          <h2 id="documents-heading" tabIndex={-1}>
            Your documents
          </h2>
          <p>{run.document.message}</p>
          {run.document.fallback && <PlainNote />}
          {run.document.missing.length > 0 && (
            <Link to="/documents" className="button button-primary">
              Go to documents
            </Link>
          )}
        </section>
      )}
      {run.step === "gate" && run.gate && <Gate run={run} gate={run.gate} />}
    </>
  );
}

function PlainNote() {
  return <p className="plain-note">{PLAIN}</p>;
}

function Gate({ run, gate }: { run: Run; gate: NonNullable<Run["gate"]> }) {
  return (
    <section className="panel" aria-labelledby="gate-heading">
      <h2 id="gate-heading" tabIndex={-1}>
        Before you approve
      </h2>
      {run.inputs_changed && (
        <p className="notice">
          Your inputs changed; please review and approve again.
        </p>
      )}
      <dl className="gate-figures">
        <dt>Tax year</dt>
        <dd>{run.tax_year}</dd>
        <dt>On the Active Taxpayers' List</dt>
        <dd>{gate.on_atl ? "Yes" : "No"}</dd>
        <dt>Taxable salary</dt>
        <dd>{rupees(gate.figures.taxable_salary)}</dd>
        <dt>Tax deducted by employers</dt>
        <dd>{rupees(gate.figures.tax_deducted)}</dd>
        <dt>Bank profit</dt>
        <dd>{rupees(gate.figures.gross_profit)}</dd>
        <dt>Tax withheld by banks</dt>
        <dd>{rupees(gate.figures.tax_withheld)}</dd>
      </dl>
      {run.validation && (
        <>
          <h3>Your figures</h3>
          <p>{run.validation.message}</p>
          {run.validation.fallback && <PlainNote />}
          {run.validation.issues.length > 0 && (
            <ul className="issues">
              {run.validation.issues.map((issue) => (
                <li key={`${issue.document_id} ${issue.field}`}>
                  {issue.certificate}: {issue.reason}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {run.research && (
        <>
          <h3>The law that applies</h3>
          <p>{run.research.note}</p>
          {run.research.fallback && <PlainNote />}
          <Sources passages={run.research.passages} />
        </>
      )}
    </section>
  );
}

/** The run's result (004's display), the passages it rests on, and Mark done. */
function ResultView({
  run,
  busy,
  focusOnLoad,
  onFocused,
  onDone,
  onRefused,
}: {
  run: Run;
  busy: boolean;
  focusOnLoad: boolean;
  onFocused: () => void;
  onDone: () => void;
  /** The result was refused (e.g. inputs changed since the approval): reload the run. */
  onRefused: () => void;
}) {
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let current = true;
    getResult()
      .then((loaded) => current && setResult(loaded))
      .catch((caught: unknown) => {
        if (!current) return;
        if (caught instanceof ApiError && caught.status === 409) {
          onRefused();
        } else {
          setError(message(caught));
        }
      });
    return () => {
      current = false;
    };
  }, [run.approved_at, onRefused]);

  useEffect(() => {
    if (result !== null && focusOnLoad) {
      heading.current?.focus();
      onFocused();
    }
  }, [result, focusOnLoad, onFocused]);

  if (error !== null) return <p role="alert">{error}</p>;
  if (result === null) return <p role="status">Calculating…</p>;
  return (
    <>
      <h2 id="result-heading" ref={heading} tabIndex={-1}>
        Your result
      </h2>
      <TaxResultView result={result} pdfUrl={WORKFLOW_PDF_URL} />
      {result.passages.length > 0 && (
        <section className="panel" aria-labelledby="sources-heading">
          <h2 id="sources-heading">The law it rests on</h2>
          <Sources passages={result.passages} />
        </section>
      )}
      {run.step === "done" ? (
        <p id="done-notice" className="notice" tabIndex={-1}>
          Done on {dateOf(run.done_at)}.
        </p>
      ) : (
        <button
          type="button"
          className="button-primary"
          aria-disabled={busy}
          onClick={onDone}
        >
          Mark done
        </button>
      )}
    </>
  );
}

/** "12 Nov 2026". */
function dateOf(timestamp: string | null): string {
  return timestamp === null
    ? ""
    : new Date(timestamp).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
}

function Sources({ passages }: { passages: Passage[] }) {
  if (passages.length === 0) return null;
  return (
    <ul className="sources" aria-label="Where this comes from" role="list">
      {passages.map((passage) => (
        <li key={passage.id}>
          <span className="badge" data-kind={passage.kind}>
            {passage.kind === "law" ? "Law" : "Guidance"}
          </span>{" "}
          {passage.source}, {passage.location}, page {passage.page}
        </li>
      ))}
    </ul>
  );
}
