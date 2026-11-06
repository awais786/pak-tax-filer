import { useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";

/**
 * Logs out (ending the session on the server) and returns to the login page (task T028).
 * If the server can't be reached, it says so: the session is still alive, so the user must not
 * be shown the login page as if they had logged out (frontend review M3).
 */
export function LogoutButton() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [failed, setFailed] = useState(false);

  async function handleClick() {
    setFailed(false);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setFailed(true);
    }
  }

  return (
    <>
      <button type="button" onClick={handleClick}>
        Log out
      </button>
      {failed && <p role="alert">Couldn't log out, try again.</p>}
    </>
  );
}
