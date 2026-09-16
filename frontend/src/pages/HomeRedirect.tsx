import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { homeFor } from "../auth/guards";

/**
 * /redirect — sends an authenticated user to their role's home.
 * Used after login/register so role logic lives in one place.
 */
export default function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <div className="page-loading">Loading…</div>;
  return <Navigate to={homeFor(user?.role)} replace />;
}
