import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getTax, taxPdfUrl } from "../api/tax";
import type { TaxResult } from "../api/tax";
import { TaxResultView } from "../components/TaxResultView";
import { useProfile } from "../profile/ProfileContext";

// The user's tax for the profile's tax year (feature 004, tasks T013, T019, T023). Every figure
// and every refusal comes from the backend, which recalculates from confirmed certificates and
// the profile's ATL status; this page only displays them (constitution, Principles I and IV).

export function TaxPage() {
  const { profile } = useProfile();
  // RequireProfile renders this page only once the profile has loaded.
  const taxYear = profile?.tax_year ?? "";
  const [result, setResult] = useState<TaxResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shownYear, setShownYear] = useState(taxYear);

  // A different year: forget the previous result (React's reset-on-change pattern).
  if (taxYear !== shownYear) {
    setShownYear(taxYear);
    setResult(null);
    setError(null);
  }

  useEffect(() => {
    let current = true;
    if (taxYear === "") {
      return;
    }
    getTax(taxYear)
      .then((loaded) => current && setResult(loaded))
      .catch((caught: unknown) => {
        if (current) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Couldn't load your tax. Check your connection and try again.",
          );
        }
      });
    return () => {
      current = false;
    };
  }, [taxYear]);

  return (
    <main>
      <h1>Your tax for {taxYear}</h1>
      {error !== null && <p role="alert">{error}</p>}
      {result === null && error === null && (
        <>
          <p role="status">Calculating…</p>
          {/* The shape of the result while it loads (task T062). */}
          <div className="headline-pair" aria-hidden="true">
            <div className="skeleton skeleton-card" />
            <div className="skeleton skeleton-card" />
          </div>
        </>
      )}
      {result !== null && (
        <TaxResultView result={result} pdfUrl={taxPdfUrl(result.tax_year)} />
      )}
    </main>
  );
}
