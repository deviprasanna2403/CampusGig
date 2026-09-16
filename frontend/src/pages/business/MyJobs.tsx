import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listMyJobs, jobAction, type JobAction } from "../../api/jobs";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/jobs/StatusBadge";

/** Which lifecycle action is legal from which status (mirrors the backend map). */
const ACTIONS_BY_STATUS: Record<string, JobAction[]> = {
  DRAFT: ["publish"],
  PUBLISHED: ["close", "cancel"],
  OPEN: ["close", "cancel"],
  FULL: ["reopen", "close", "cancel"],
  CLOSED: ["reopen", "cancel"],
  EXPIRED: [],
  CANCELLED: [],
};

const ACTION_LABEL: Record<JobAction, string> = {
  publish: "Publish",
  close: "Close",
  cancel: "Cancel",
  reopen: "Reopen",
};

export default function MyJobs() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: JobAction } | null>(null);

  const jobsQ = useQuery({
    queryKey: ["my-jobs", status, page],
    queryFn: () => listMyJobs({ status: status || undefined, page }),
    placeholderData: keepPreviousData,
  });

  const actionM = useMutation({
    mutationFn: ({ id, action }: { id: string; action: JobAction }) => jobAction(id, action),
    onSuccess: () => {
      setActionError(null);
      setConfirming(null);
      queryClient.invalidateQueries({ queryKey: ["my-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["business-analytics"] });
    },
    onError: (err) => {
      setConfirming(null);
      setActionError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Action failed.");
    },
  });

  return (
    <section>
      <div className="list-head">
        <h1>My jobs</h1>
        <div className="list-head-actions">
          <label className="inline-select">
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All statuses</option>
              {Object.keys(ACTIONS_BY_STATUS).map((s) => (
                <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
              ))}
            </select>
          </label>
          <Link className="btn primary" to="/business/jobs/new">+ New job</Link>
        </div>
      </div>

      {actionError && <div className="form-error">{actionError}</div>}

      {jobsQ.isLoading && <div className="page-loading">Loading jobs…</div>}
      {jobsQ.isError && <ErrorState error={jobsQ.error} retry={() => jobsQ.refetch()} />}

      {jobsQ.data && (
        <>
          <div className="app-list">
            {jobsQ.data.results.map((job) => {
              const actions = ACTIONS_BY_STATUS[job.status] ?? [];
              return (
                <article key={job.id} className="card app-row">
                  <div className="app-row-main">
                    <h3>
                      <Link to={`/business/jobs/${job.id}/edit`}>{job.title}</Link>
                    </h3>
                    <p className="muted small">
                      {job.category?.name ?? "Uncategorized"} · ₹{job.payment_amount}
                      {" "}
                      {job.payment_type === "HOURLY" ? "/hr" : job.payment_type.replaceAll("_", " ").toLowerCase()} ·
                      apply by {job.application_deadline}
                    </p>
                  </div>
                  <div className="app-row-side">
                    <StatusBadge status={job.status} />
                    <div className="action-row">
                      <Link className="btn ghost" to={`/business/jobs/${job.id}/applicants`}>
                        Applicants
                      </Link>
                      {actions.map((a) => (
                        <button
                          key={a}
                          className={`btn ${a === "cancel" ? "danger" : "ghost"}`}
                          disabled={actionM.isPending}
                          onClick={() => setConfirming({ id: job.id, action: a })}
                        >
                          {ACTION_LABEL[a]}
                        </button>
                      ))}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          {jobsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">No jobs yet — create your first posting.</p>
              <Link className="btn primary" to="/business/jobs/new">+ New job</Link>
            </div>
          )}
          <Pagination count={jobsQ.data.count} page={page} onPage={setPage} />
        </>
      )}

      {confirming && (
        <div className="modal-backdrop" onClick={() => setConfirming(null)}>
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <h2>{ACTION_LABEL[confirming.action]} this job?</h2>
            <p className="muted">
              {confirming.action === "cancel"
                ? "Cancelling notifies every applicant. This cannot be undone."
                : `This moves the job to ${confirming.action === "publish" ? "PUBLISHED" : confirming.action.toUpperCase() + "ED"} state.`}
            </p>
            <div className="modal-actions">
              <button className="btn ghost" onClick={() => setConfirming(null)}>Keep as is</button>
              <button
                className={`btn ${confirming.action === "cancel" ? "danger" : "primary"}`}
                disabled={actionM.isPending}
                onClick={() => actionM.mutate(confirming)}
              >
                {actionM.isPending ? "Working…" : `Yes, ${ACTION_LABEL[confirming.action].toLowerCase()}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
