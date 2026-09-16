import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { studentAnalytics } from "../../api/analytics";
import { useAuth } from "../../auth/AuthContext";
import ErrorState from "../../components/ErrorState";

/**
 * Student dashboard — real Phase 9B data from analytics/student/me/:
 * profile completion, application counts/success rate, open jobs near
 * campus. (Recommendations join in Phase F4.)
 */
export default function StudentHome() {
  const { user } = useAuth();
  const statsQ = useQuery({ queryKey: ["student-analytics"], queryFn: () => studentAnalytics() });

  if (statsQ.isLoading) return <div className="page-loading">Loading your dashboard…</div>;
  if (statsQ.isError) return <ErrorState error={statsQ.error} retry={() => statsQ.refetch()} />;

  const s = statsQ.data!;

  return (
    <section>
      <h1>Welcome{user ? `, ${user.email.split("@")[0]}` : ""} 👋</h1>
      <p className="muted">Your campus gig activity at a glance.</p>

      <div className="stat-grid">
        <div className="card stat">
          <span className="stat-num">{s.applications.total}</span>
          <span className="stat-label">Applications</span>
          <Link className="stat-link" to="/student/applications">View →</Link>
        </div>
        <div className="card stat">
          <span className="stat-num">{s.applications.success_rate === null ? "—" : `${Math.round(s.applications.success_rate * 100)}%`}</span>
          <span className="stat-label">Success rate</span>
          <span className="stat-sub muted small">{s.completed_gigs} selected</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{s.open_jobs_near_campus}</span>
          <span className="stat-label">Open jobs near campus</span>
          <Link className="stat-link" to="/student/jobs">Browse →</Link>
        </div>
        <div className="card stat">
          <span className="stat-num">{s.profile_completion_percentage}%</span>
          <span className="stat-label">Profile complete</span>
          <Link className="stat-link" to="/student/profile">Improve →</Link>
        </div>
      </div>

      {s.rating_average !== null && (
        <p className="muted small">Your average rating: {s.rating_average} ★</p>
      )}
    </section>
  );
}
