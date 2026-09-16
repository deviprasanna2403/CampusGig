import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listBusinessApplications, updateApplicationStatus } from "../../api/applications";
import { listMyJobs } from "../../api/jobs";
import type { ApplicationStatus } from "../../api/types";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/jobs/StatusBadge";

/** Allowed business transitions (WITHDRAWN is student-only; backend validates). */
const NEXT_STATUS: Record<string, ApplicationStatus[]> = {
  SUBMITTED: ["SHORTLISTED", "INTERVIEW", "SELECTED", "REJECTED"],
  SHORTLISTED: ["INTERVIEW", "SELECTED", "REJECTED"],
  INTERVIEW: ["SELECTED", "REJECTED"],
  SELECTED: [],
  REJECTED: [],
  WITHDRAWN: [],
};

const STATUS_OPTIONS: [ApplicationStatus | "", string][] = [
  ["", "All statuses"],
  ["SUBMITTED", "Submitted"],
  ["SHORTLISTED", "Shortlisted"],
  ["INTERVIEW", "Interview"],
  ["SELECTED", "Selected"],
  ["REJECTED", "Rejected"],
  ["WITHDRAWN", "Withdrawn"],
];

export default function Applicants() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const jobFilter = params.get("job") ?? "";
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const jobsQ = useQuery({ queryKey: ["my-jobs", "", 1], queryFn: () => listMyJobs({ page: 1 }), staleTime: 60_000 });

  const appsQ = useQuery({
    queryKey: ["business-applications", jobFilter, status, page],
    queryFn: () =>
      listBusinessApplications({ job: jobFilter || undefined, status: status || undefined, page }),
    placeholderData: keepPreviousData,
  });

  const statusM = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) =>
      updateApplicationStatus(id, status),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["business-applications"] });
      queryClient.invalidateQueries({ queryKey: ["business-analytics"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not update status."),
  });

  return (
    <section>
      <div className="list-head">
        <h1>Applicants</h1>
        <div className="list-head-actions">
          <label className="inline-select">
            <select
              value={jobFilter}
              onChange={(e) => { const v = e.target.value; setParams(v ? { job: v } : {}); setPage(1); }}
            >
              <option value="">All my jobs</option>
              {(jobsQ.data?.results ?? []).map((j) => (
                <option key={j.id} value={j.id}>{j.title}</option>
              ))}
            </select>
          </label>
          <label className="inline-select">
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {error && <div className="form-error">{error}</div>}

      {appsQ.isLoading && <div className="page-loading">Loading applicants…</div>}
      {appsQ.isError && <ErrorState error={appsQ.error} retry={() => appsQ.refetch()} />}

      {appsQ.data && (
        <>
          <div className="app-list">
            {appsQ.data.results.map((a) => {
              const nexts = NEXT_STATUS[a.status] ?? [];
              return (
                <article key={a.id} className="card app-row">
                  <div className="app-row-main">
                    <h3>{a.student}</h3>
                    <p className="muted small">
                      {a.job} · applied {new Date(a.submitted_at).toLocaleDateString()}
                    </p>
                    {a.cover_note && <p className="cover-note">“{a.cover_note}”</p>}
                  </div>
                  <div className="app-row-side">
                    <StatusBadge status={a.status} />
                    {nexts.length > 0 && (
                      <div className="action-row">
                        {nexts.map((s) => (
                          <button
                            key={s}
                            className={`btn ${s === "REJECTED" ? "danger" : s === "SELECTED" ? "primary" : "ghost"}`}
                            disabled={statusM.isPending}
                            onClick={() => statusM.mutate({ id: a.id, status: s })}
                          >
                            {s === "SHORTLISTED" ? "Shortlist" : s === "INTERVIEW" ? "Interview" : s.charAt(0) + s.slice(1).toLowerCase()}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
          {appsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">No applications{jobFilter ? " for this job" : ""} yet.</p>
              <Link className="btn ghost" to="/business/jobs">Manage jobs</Link>
            </div>
          )}
          <Pagination count={appsQ.data.count} page={page} onPage={setPage} />
        </>
      )}
    </section>
  );
}
