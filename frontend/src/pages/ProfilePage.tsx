import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import { LogoutButton } from "../components/LogoutButton";
import { useProfile } from "../profile/ProfileContext";
import { ProfileLoadError } from "../profile/ProfileLoadError";
import { safeNext } from "../navigation";

// Taxpayer profile setup and edit, per specs/002-auth-foundation/contracts/cli-and-ui.md
// (task T041; research R12 for the FBR link).

const FBR_ATL_PAGE =
  "https://www.fbr.gov.pk/categ/active-taxpayer-list-income-tax/51147/30859/71169";

export function ProfilePage() {
  const {
    profile,
    supportedTaxYears,
    loading,
    error: loadError,
    save,
  } = useProfile();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [taxYear, setTaxYear] = useState<string | null>(null);
  const [onAtl, setOnAtl] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (loadError !== null) {
    return <ProfileLoadError />;
  }
  if (loading) {
    return <p role="status">Loading…</p>;
  }

  // Until the user picks, show the saved answers (editing) or the first supported year.
  const chosenYear = taxYear ?? profile?.tax_year ?? supportedTaxYears[0] ?? "";
  const chosenAtl = onAtl ?? profile?.on_atl ?? null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (chosenAtl === null) {
      setError("Tell us whether you are on the ATL.");
      return;
    }
    setSaving(true);
    try {
      await save(chosenYear, chosenAtl);
      navigate(safeNext(searchParams.get("next")), { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong. Try again.",
      );
      setSaving(false);
    }
  }

  return (
    <main>
      <h1>{profile ? "Your profile" : "Set up your profile"}</h1>
      <p>This app covers people who live in Pakistan and earn a salary.</p>
      <form onSubmit={handleSubmit}>
        <label>
          Tax year
          <select
            value={chosenYear}
            onChange={(event) => setTaxYear(event.target.value)}
          >
            {supportedTaxYears.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
        <fieldset aria-describedby={error ? "profile-error" : undefined}>
          <legend>Are you on FBR's Active Taxpayers' List (ATL)?</legend>
          <label>
            <input
              type="radio"
              name="on_atl"
              checked={chosenAtl === true}
              onChange={() => setOnAtl(true)}
            />
            Yes
          </label>
          <label>
            <input
              type="radio"
              name="on_atl"
              checked={chosenAtl === false}
              onChange={() => setOnAtl(false)}
            />
            No
          </label>
          <p>
            <a href={FBR_ATL_PAGE} target="_blank" rel="noopener noreferrer">
              Check your ATL status on FBR's website
              <span className="visually-hidden"> (opens in a new tab)</span>
            </a>
          </p>
        </fieldset>
        {error && (
          <p id="profile-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={saving}>
          Save
        </button>
      </form>
      <LogoutButton />
    </main>
  );
}
