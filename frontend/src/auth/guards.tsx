import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import type { Role } from "../api/types";

/** Where each role lands after login (also used by Login on success). */
export function homeFor(role: Role | undefined | null): string {
  switch (role) {
    case "student":
      return "/student";
    case "business":
      return "/business";
    case "admin":
      return "/admin";
    default:
      return "/login";
  }
}

/** Requires any authenticated session. */
export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

/** Requires one of the given roles; wrong role goes to their own home. */
export function RoleRoute({ allow }: { allow: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!allow.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
