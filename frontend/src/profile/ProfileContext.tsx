import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { ApiError, apiFetch } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// The logged-in user's taxpayer profile, from GET /api/profile (feature 002, task T041).

export type Profile = { tax_year: string; on_atl: boolean; updated_at: string };

type ProfileReply = { profile: Profile | null; supported_tax_years: string[] };

type ProfileState = {
  profile: Profile | null;
  supportedTaxYears: string[];
  /** True while the profile is being loaded for the logged-in user. */
  loading: boolean;
  /** Set when loading failed for a reason other than being logged out; `retry` tries again. */
  error: string | null;
  retry: () => void;
  save: (taxYear: string, onAtl: boolean) => Promise<void>;
};

const ProfileContext = createContext<ProfileState | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [reply, setReply] = useState<ProfileReply | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [previousUser, setPreviousUser] = useState(user);

  // Forget the previous user's profile at logout or when someone else logs in (review L1).
  // React's pattern for resetting state when an input changes: compare during render.
  if (user !== previousUser) {
    setPreviousUser(user);
    setReply(null);
    setLoadedFor(null);
    setError(null);
  }

  useEffect(() => {
    let current = true;
    if (user === null) {
      return;
    }
    apiFetch<ProfileReply>("/api/profile")
      .then((data) => {
        if (current) {
          setReply(data);
          setLoadedFor(user.email);
        }
      })
      .catch((caught: unknown) => {
        // A 401 is handled by the API helper (back to login). Anything else is shown with a
        // retry, instead of "Loading…" forever (review M2).
        if (current && !(caught instanceof ApiError && caught.status === 401)) {
          setError(
            "Couldn't load your profile. Check your connection and try again.",
          );
        }
      });
    return () => {
      current = false;
    };
  }, [user, attempt]);

  const retry = useCallback(() => {
    setError(null);
    setAttempt((count) => count + 1);
  }, []);

  const save = useCallback(async (taxYear: string, onAtl: boolean) => {
    const profile = await apiFetch<Profile>("/api/profile", {
      method: "PUT",
      body: { tax_year: taxYear, on_atl: onAtl },
    });
    setReply((previous) => ({
      profile,
      supported_tax_years: previous?.supported_tax_years ?? [profile.tax_year],
    }));
  }, []);

  const value = useMemo(
    () => ({
      // Only show a profile loaded for the user who is logged in now.
      profile:
        user !== null && loadedFor === user.email
          ? (reply?.profile ?? null)
          : null,
      supportedTaxYears: reply?.supported_tax_years ?? [],
      loading: user !== null && loadedFor !== user.email && error === null,
      error,
      retry,
      save,
    }),
    [user, loadedFor, reply, error, retry, save],
  );
  return (
    <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
  );
}

// The hook lives beside its provider, as React's own docs show.
// eslint-disable-next-line react/only-export-components
export function useProfile(): ProfileState {
  const state = useContext(ProfileContext);
  if (state === null) {
    throw new Error("useProfile must be used inside <ProfileProvider>.");
  }
  return state;
}
