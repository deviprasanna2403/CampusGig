import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getJob } from "../../api/jobs";
import { applyToJob } from "../../api/applications";
import { trackEngagement } from "../../api/matching";
import { createReport, listMyReports, type ReportCategory } from "../../api/safety";
import { useAuth } from "../../auth/AuthContext";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";
import ReviewsList from "../../components/reviews/ReviewsList";
import StatusBadge from "../../components/jobs/StatusBadge";

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [coverNote, setCoverNote] = useState("");
  const [applyError, setApplyError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);
  const [reportCategory, setReportCategory] = useState<ReportCategory>("FAKE_JOB");
  const [reportDescription, setReportDescription] = useState("");
  const [reportError, setReportError] = useState<string | null>(null);
  const [reported, setReported] = useState(false);

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

  const myReportsQ = useQuery({
    queryKey: ["my-reports"],
    queryFn: () => listMyReports(),
    enabled: user?.role === "student",
    staleTime: 30_000,
  });
  const alreadyReported =
    !!id && (myReportsQ.data?.results ?? []).some((r) => r.target_type === "JOB" && r.target_id === id);

  const reportM = useMutation({
    mutationFn: () =>
      createReport({
        target_type: "JOB",
        target_id: id!,
        category: reportCategory,
        description: reportDescription.trim(),
      }),
    onSuccess: () => {
      setReportError(null);
      setReported(true);
      queryClient.invalidateQueries({ queryKey: ["my-reports"] });
    },
    onError: (err) =>
      setReportError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not submit report."),
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

        {job.business_user_id && (
          <>
            <h2>About the business</h2>
            <ReviewsList
              userId={job.business_user_id}
              emptyText="No reviews yet for this business."
              max={3}
            />
          </>
        )}
      </div>

      {user?.role === "student" && (
        <div className="card">
          <h2>Something wrong with this job?</h2>
          {reported || alreadyReported ? (
            <p className="success-note">
              Thanks — your report is with our safety team. Reviewed reports can lead to the
              listing being taken down.
            </p>
          ) : showReport ? (
            <div className="report-form">
              {reportError && <div className="form-error">{reportError}</div>}
              <label>
                What is wrong?
                <select
                  value={reportCategory}
                  disabled={reportM.isPending}
                  onChange={(e) => setReportCategory(e.target.value as ReportCategory)}
                >
                  <option value="FAKE_JOB">Fake job or scam</option>
                  <option value="PAYMENT_ISSUE">Payment problem</option>
                  <option value="HARASSMENT">Harassment</option>
                  <option value="INAPPROPRIATE_CONTENT">Inappropriate content</option>
                  <option value="OTHER">Something else</option>
                </select>
              </label>
              <label>
                Describe the issue (at least 10 characters)
                <textarea
                  rows={3}
                  maxLength={2000}
                  placeholder="Tell the safety team what happened."
                  value={reportDescription}
                  disabled={reportM.isPending}
                  onChange={(e) => setReportDescription(e.target.value)}
                />
              </label>
              <div className="action-row">
                <button
                  className="btn primary"
                  disabled={reportM.isPending || reportDescription.trim().length < 10}
                  onClick={() => reportM.mutate()}
                >
                  {reportM.isPending ? "Submitting…" : "Submit report"}
                </button>
                <button className="btn ghost" disabled={reportM.isPending} onClick={() => setShowReport(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p className="muted small">
              Flag this listing for the safety team — reports are confidential.{" "}
              <button className="btn ghost" onClick={() => setShowReport(true)}>
                Report this job
              </button>
            </p>
          )}
        </div>
      )}

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
