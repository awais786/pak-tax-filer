import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useProfile } from "./ProfileContext";
import { ProfileLoadError } from "./ProfileLoadError";

/**
 * Pages that need the taxpayer profile (all logged-in pages except /profile): users without
 * one go to /profile?next=<this page> first (FR-020). The backend enforces it too.
 */
export function RequireProfile({ children }: { children: ReactNode }) {
  const { profile, loading, error } = useProfile();
  const location = useLocation();

  if (error !== null) {
    return <ProfileLoadError />;
  }
  if (loading) {
    return <p role="status">Loading…</p>;
  }
  if (profile === null) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/profile?next=${next}`} replace />;
  }
  return children;
}
