import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

/**
 * F1 shell: topbar with brand, role badge, account email, sign-out.
 * Per-role navigation links arrive with each role's phase (F2–F5).
 */
export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function onSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <Link to="/redirect" className="brand small">CampusGig</Link>
          {user?.role === "student" && (
            <nav className="main-nav">
              <NavLink to="/student/jobs">Jobs</NavLink>
              <NavLink to="/student/applications">Applications</NavLink>
              <NavLink to="/student/profile">Profile</NavLink>
            </nav>
          )}
        </div>
        <div className="topbar-right">
          {user && (
            <>
              <span className={`role-badge role-${user.role}`}>{user.role}</span>
              <span className="user-email">{user.email}</span>
              <button className="btn ghost" type="button" onClick={onSignOut}>
                Sign out
              </button>
            </>
          )}
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
