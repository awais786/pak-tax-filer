import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { ProfileProvider } from "../profile/ProfileContext";

/** Render the whole app at a path, as the browser would (router + auth state + routes). */
export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ProfileProvider>
          <AppRoutes />
        </ProfileProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
