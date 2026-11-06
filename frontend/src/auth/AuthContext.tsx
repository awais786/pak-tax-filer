import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { apiFetch, setSessionEndedHandler } from "../api/client";

// Who is logged in, loaded from GET /api/auth/me (feature 002, task T026, research R9).
// The real session is the HttpOnly cookie; nothing is kept in local storage.

export type User = { email: string };

export const SESSION_ENDED = "Your session has ended, please log in again.";

type AuthState = {
  user: User | null;
  /** True until the first "who am I" check has answered. */
  loading: boolean;
  /** A message for the login page, e.g. after the session ended. */
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const navigate = useNavigate();
  const userRef = useRef<User | null>(null);

  useEffect(() => {
    // Kept in a ref so the session-ended handler below always sees the current user.
    userRef.current = user;
  }, [user]);

  useEffect(() => {
    // Any API call that finds the session gone sends the user to log in again (FR-013). A late
    // 401 arriving after a deliberate logout isn't a "session ended" (frontend review L3).
    setSessionEndedHandler(() => {
      if (userRef.current === null) {
        return;
      }
      setUser(null);
      setNotice(SESSION_ENDED);
      navigate("/login", { replace: true });
    });
  }, [navigate]);

  useEffect(() => {
    // The first check is quiet: being logged out on arrival isn't a "session ended".
    apiFetch<User>("/api/auth/me", { allowUnauthenticated: true })
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const loggedIn = await apiFetch<User>("/api/auth/login", {
      method: "POST",
      body: { email, password },
      allowUnauthenticated: true,
    });
    setNotice(null);
    setUser(loggedIn);
  }, []);

  const logout = useCallback(async () => {
    await apiFetch<void>("/api/auth/logout", {
      method: "POST",
      allowUnauthenticated: true,
    });
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, notice, login, logout }),
    [user, loading, notice, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The hook lives beside its provider, as React's own docs show.
// eslint-disable-next-line react/only-export-components
export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (state === null) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }
  return state;
}
