import { Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import {
  AppFrame,
  AuthFrame,
  PlainFrame,
  ProfileFrame,
} from "./components/AppFrame";
import { AskPage } from "./pages/AskPage";
import { CalculatorPage } from "./pages/CalculatorPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ReviewPage } from "./pages/ReviewPage";
import { SignupPage } from "./pages/SignupPage";
import { TaxPage } from "./pages/TaxPage";
import { WealthPage } from "./pages/WealthPage";
import { WorkflowPage } from "./pages/WorkflowPage";
import { RequireProfile } from "./profile/RequireProfile";

/**
 * The app's pages (feature 002 tasks T029, T041; feature 003 tasks T015, T019; feature 004 task
 * T013), each inside its frame (feature 001 task T050). Every logged-in page except /profile
 * also needs the taxpayer profile. main.tsx provides the router, AuthProvider and
 * ProfileProvider.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AuthFrame />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>
      <Route
        path="/profile"
        element={
          <RequireAuth>
            <ProfileFrame>
              <ProfilePage />
            </ProfileFrame>
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <RequireProfile>
              <AppFrame />
            </RequireProfile>
          </RequireAuth>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/:id" element={<ReviewPage />} />
        <Route path="/tax" element={<TaxPage />} />
        <Route path="/calculator" element={<CalculatorPage />} />
        <Route path="/wealth" element={<WealthPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/workflow" element={<WorkflowPage />} />
      </Route>
      <Route element={<PlainFrame />}>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
