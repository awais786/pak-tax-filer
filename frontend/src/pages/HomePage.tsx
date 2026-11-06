import { useEffect, useState } from "react";
import { Link } from "react-router";
import { apiFetch } from "../api/client";
import type { User } from "../auth/AuthContext";
import { LogoutButton } from "../components/LogoutButton";

/**
 * The protected home page (task T028). It asks the API who is logged in, so a session that
 * ended elsewhere is noticed here and the user is sent back to log in (FR-013).
 */
export function HomePage() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        // A 401 is handled by the API helper (back to login); nothing else to do here.
      });
  }, []);

  return (
    <main>
      <h1>pak-tax-filer</h1>
      {user && <p>Logged in as {user.email}</p>}
      <nav>
        <Link to="/profile">Profile</Link> <LogoutButton />
      </nav>
    </main>
  );
}
