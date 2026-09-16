import { Outlet, useNavigate } from "react-router-dom";
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
        <span className="brand small">CampusGig</span>
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
