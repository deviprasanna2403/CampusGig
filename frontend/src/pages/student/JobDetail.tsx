import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getJob } from "../../api/jobs";
import { applyToJob } from "../../api/applications";
import { trackEngagement } from "../../api/matching";
import { useAuth } from "../../auth/AuthContext";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";
import StatusBadge from "../../components/jobs/StatusBadge";

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [coverNote, setCoverNote] = useState("");
  const [applyError, setApplyError] = useState<string | null>(null);

  // Fire-and-forget engagement signal for matching (Phase 7); failures ignored.
  useEffect(() => {
    if (user?.role === "student" && id) {
      trackEngagement(id, "VIEWED").catch(() => undefined);
    }
  }, [user?.role, id]);

  const jobQ = useQuery({
    queryKey: ["job", id],
    queryFn: () => getJob(id!),
    enabled: !!id,
    retry: false,
  });

  const applyM = useMutation({
    mutationFn: () => applyToJob(id!, coverNote.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-applications"] });
      navigate("/student/applications", { state: { applied: true } });
    },
    onError: (err) =>
      setApplyError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not submit application."),
  });

  if (jobQ.isLoading) return <div className="page-loading">Loading job…</div>;
  if (jobQ.isError) return <ErrorState error={jobQ.error} retry={() => jobQ.refetch()} />;

  const job = jobQ.data!;

  return (
    <section className="job-detail">
      <Link to="/student" className="muted small">← Back to jobs</Link>
      <div className="card">
        <div className="job-card-head">
          <h1>{job.title}</h1>
          <StatusBadge status={job.status} />
        </div>
        <p className="job-meta">
          {job.category?.name ?? "Uncategorized"} · posted by {job.business}
        </p>
        <p>{job.description}</p>

        <dl className="detail-grid">
          <div><dt>Payment</dt><dd>₹{job.payment_amount} ({job.payment_type.replaceAll("_", " ").toLowerCase()})</dd></div>
          <div><dt>Dates</dt><dd>{job.start_date} → {job.end_date}</dd></div>
          <div><dt>Hours</dt><dd>{job.start_time} – {job.end_time}</dd></div>
          <div><dt>Workers needed</dt><dd>{job.workers_required}</dd></div>
          <div><dt>Apply by</dt><dd>{job.application_deadline}</dd></div>
          <div><dt>Eligibility</dt><dd>{job.eligibility_notes || "—"}</dd></div>
        </dl>

        {job.required_skills.length > 0 && (
          <>
            <h2>Required skills</h2>
            <p className="skill-tags">
              {job.required_skills.map((s) => (
                <span key={s.id} className="skill-tag">{s.name}</span>
              ))}
            </p>
          </>
        )}
      </div>

      <div className="card">
        <h2>Apply for this job</h2>
        {applyError && <div className="form-error">{applyError}</div>}
        <label>
          Cover note (optional)
          <textarea
            rows={4}
            maxLength={1000}
            placeholder="Why are you a good fit?"
            value={coverNote}
            onChange={(e) => setCoverNote(e.target.value)}
          />
        </label>
        <button className="btn primary" onClick={() => applyM.mutate()} disabled={applyM.isPending}>
          {applyM.isPending ? "Submitting…" : "Submit application"}
        </button>
        <p className="muted small">
          One application per job — the platform rejects duplicates automatically.
        </p>
      </div>
    </section>
  );
}
