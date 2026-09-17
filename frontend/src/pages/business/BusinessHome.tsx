import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { businessAnalytics } from "../../api/analytics";
import { getMyBusinessProfile } from "../../api/profiles";
import { getMyVerification } from "../../api/safety";
import { useAuth } from "../../auth/AuthContext";
import ErrorState from "../../components/ErrorState";
import ReviewsList from "../../components/reviews/ReviewsList";
import StatusBadge from "../../components/jobs/StatusBadge";

const VERIFICATION_COPY: Record<string, { text: string; tone: "warn" | "success" | "info" }> = {
  SUBMITTED: { text: "Verification submitted — an admin will review your documents.", tone: "info" },
  UNDER_REVIEW: { text: "Your verification is under review.", tone: "info" },
  VERIFIED: { text: "Your business is verified — you can publish jobs.", tone: "success" },
  REJECTED: { text: "Verification was rejected — update your details to resubmit.", tone: "warn" },
  REVOKED: { text: "Your verification was revoked — contact support.", tone: "warn" },
};

export default function BusinessHome() {
  const { user } = useAuth();
  const statsQ = useQuery({ queryKey: ["business-analytics"], queryFn: () => businessAnalytics() });
  const profileQ = useQuery({ queryKey: ["business-profile"], queryFn: getMyBusinessProfile });
  const verifQ = useQuery({ queryKey: ["verification"], queryFn: getMyVerification });

  if (statsQ.isLoading) return <div className="page-loading">Loading your dashboard…</div>;
  if (statsQ.isError) return <ErrorState error={statsQ.error} retry={() => statsQ.refetch()} />;

  const s = statsQ.data!;
  const verif = verifQ.data;
  const verifCopy = verif ? VERIFICATION_COPY[verif.status] : null;

  return (
    <section>
      <h1>{profileQ.data?.business_name || "Business console"}</h1>
      <p className="muted">Welcome{user ? `, ${user.email.split("@")[0]}` : ""} — your hiring activity at a glance.</p>

      {verif && verifCopy && verif.status !== "VERIFIED" && (
        <div className={`banner ${verifCopy.tone}`}>
          <StatusBadge status={verif.status} />
          <span>{verifCopy.text}</span>
          <Link className="btn ghost" to="/business/verification">
            {verif.status === "SUBMITTED" && !verif.legal_name ? "Complete verification" : "View verification"}
          </Link>
        </div>
      )}

      <div className="stat-grid">
        <div className="card stat">
          <span className="stat-num">{s.jobs.total}</span>
          <span className="stat-label">Jobs posted</span>
          <Link className="stat-link" to="/business/jobs">Manage →</Link>
        </div>
        <div className="card stat">
          <span className="stat-num">{s.applications.received}</span>
          <span className="stat-label">Applications received</span>
          <Link className="stat-link" to="/business/applicants">Review →</Link>
        </div>
        <div className="card stat">
          <span className="stat-num">
            {s.applications.selection_rate === null ? "—" : `${Math.round(s.applications.selection_rate * 100)}%`}
          </span>
          <span className="stat-label">Selection rate</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{s.rating_average ?? "—"}</span>
          <span className="stat-label">Average rating</span>
        </div>
      </div>

      {user && (
        <div className="card">
          <h2>Reviews about your business</h2>
          <ReviewsList userId={user.id} emptyText="No reviews yet — students can review you after completed gigs." max={3} />
        </div>
      )}

      {profileQ.data && (
        <div className="banner info">
          <span>
            Profile <strong>{profileQ.data.completion_percentage}%</strong> complete
            {!profileQ.data.is_complete && " — businesses with complete profiles get better discovery"}
          </span>
          <Link className="btn ghost" to="/business/profile">Edit profile</Link>
        </div>
      )}
    </section>
  );
}
