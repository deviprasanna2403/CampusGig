import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import NotificationBell from "./NotificationBell";

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
              <NavLink to="/student/recommendations">For you</NavLink>
              <NavLink to="/student/applications">Applications</NavLink>
              <NavLink to="/messages">Messages</NavLink>
              <NavLink to="/interviews">Interviews</NavLink>
              <NavLink to="/student/profile">Profile</NavLink>
            </nav>
          )}
          {user?.role === "business" && (
            <nav className="main-nav">
              <NavLink to="/business/jobs" end>My jobs</NavLink>
              <NavLink to="/business/applicants">Applicants</NavLink>
              <NavLink to="/interviews">Interviews</NavLink>
              <NavLink to="/messages">Messages</NavLink>
              <NavLink to="/business/verification">Verification</NavLink>
              <NavLink to="/business/profile">Profile</NavLink>
            </nav>
          )}
          {user?.role === "admin" && (
            <nav className="main-nav">
              <NavLink to="/admin" end>Overview</NavLink>
              <NavLink to="/admin/verifications">Verifications</NavLink>
              <NavLink to="/admin/reports">Reports</NavLink>
              <NavLink to="/admin/reviews">Reviews</NavLink>
              <NavLink to="/admin/audit-logs">Audit log</NavLink>
            </nav>
          )}
        </div>
        <div className="topbar-right">
          {user && <NotificationBell />}
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
