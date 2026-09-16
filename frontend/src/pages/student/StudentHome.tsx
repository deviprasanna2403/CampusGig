import { useAuth } from "../../auth/AuthContext";

/**
 * Student dashboard placeholder — replaced in Phase F2 with analytics cards
 * (analytics/student/me/), recommendations, and application status.
 */
export default function StudentHome() {
  const { user } = useAuth();
  return (
    <section className="card">
      <h1>Welcome{user ? `, ${user.email}` : ""}</h1>
      <p className="muted">
        Student dashboard — job discovery, applications, and your analytics arrive in Phase F2.
      </p>
    </section>
  );
}
