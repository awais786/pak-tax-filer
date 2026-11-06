import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { AppRoutes } from "./App.tsx";
import { AuthProvider } from "./auth/AuthContext.tsx";
import { ProfileProvider } from "./profile/ProfileContext.tsx";
import "./styles.css";

// index.html always contains <div id="root">, so the element exists.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ProfileProvider>
          <AppRoutes />
        </ProfileProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
