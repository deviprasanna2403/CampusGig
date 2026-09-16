import { useAuth } from "../../auth/AuthContext";

/**
 * Business dashboard placeholder — replaced in Phase F3 with job management,
 * applicants, verification status, and analytics/business/me/.
 */
export default function BusinessHome() {
  const { user } = useAuth();
  const verified = user?.is_verified;
  return (
    <section className="card">
      <h1>Business console</h1>
      <p className="muted">
        Job management, applicants, and analytics arrive in Phase F3.
      </p>
      {!verified && (
        <p className="note">
          Your account is not verified yet — publishing jobs requires verification (Phase 9 gate).
        </p>
      )}
    </section>
  );
}
