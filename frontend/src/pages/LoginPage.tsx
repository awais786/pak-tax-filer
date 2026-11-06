import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { safeNext } from "../navigation";

// Login page, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T027).

export function LoginPage() {
  const { user, loading, notice, login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const next = safeNext(searchParams.get("next"));

  if (loading) {
    return <p role="status">Loading…</p>;
  }
  if (user !== null && !submitting) {
    return <Navigate to={next} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong. Try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Log in</h1>
      <p>
        <strong>Demo data only.</strong> Do not enter real personal information.
      </p>
      {notice && <p role="status">{notice}</p>}
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            aria-invalid={error !== null}
            aria-describedby={error ? "login-error" : undefined}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && (
          <p id="login-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          Log in
        </button>
      </form>
      <p>
        Password reset isn't available yet: this is a demo, so ask the developer
        for help.
      </p>
    </main>
  );
}
