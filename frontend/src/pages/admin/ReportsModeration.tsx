/**
 * Report moderation (Phase F5) — admin view of all safety reports
 * (GET /safety/reports/ returns everything for admins) with status
 * transitions via PATCH /safety/admin/reports/{id}/review/. Every
 * review decision is audited server-side (report.review).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listReports, reviewReport } from "../../api/admin";
import type { Report, ReportStatus } from "../../api/types";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

const STATUS_OPTIONS: [ReportStatus | "", string][] = [
  ["", "All statuses"],
  ["OPEN", "Open"],
  ["UNDER_REVIEW", "Under review"],
  ["VALID", "Valid"],
  ["DISMISSED", "Dismissed"],
  ["ACTIONED", "Actioned"],
];

function statusClass(s: ReportStatus): string {
  if (s === "VALID" || s === "ACTIONED") return "ok";
  if (s === "DISMISSED") return "muted";
  return "warn";
}

function ReviewPanel({ r }: { r: Report }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reviewM = useMutation({
    mutationFn: (status: ReportStatus) => reviewReport(r.id, { status, resolution_notes: notes || undefined }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
      queryClient.invalidateQueries({ queryKey: ["admin-analytics"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Review failed."),
  });

  const busy = reviewM.isPending;
  const terminal = r.status === "VALID" || r.status === "DISMISSED" || r.status === "ACTIONED";

  return (
    <div className="review-actions">
      {error && <p className="form-error">{error}</p>}
      <input
        type="text"
        placeholder="Resolution notes"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <div className="action-row">
        {r.status !== "UNDER_REVIEW" && r.status !== "VALID" && (
          <button className="btn ghost" disabled={busy} onClick={() => reviewM.mutate("UNDER_REVIEW")}>
            Take review
          </button>
        )}
        {!terminal && (
          <>
            <button className="btn primary" disabled={busy} onClick={() => reviewM.mutate("VALID")}>
              Mark valid
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => reviewM.mutate("DISMISSED")}>
              Dismiss
            </button>
            <button className="btn danger" disabled={busy} onClick={() => reviewM.mutate("ACTIONED")}>
              Action taken
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function ReportsModeration() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const reportsQ = useQuery({
    queryKey: ["admin-reports", status, page],
    queryFn: () => listReports({ status: (status || undefined) as ReportStatus | undefined, page }),
    placeholderData: keepPreviousData,
  });

  return (
    <section>
      <div className="list-head">
        <h1>Report moderation</h1>
        <label className="inline-select">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            {STATUS_OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
      </div>

      {reportsQ.isLoading && <div className="page-loading">Loading reports…</div>}
      {reportsQ.isError && <ErrorState error={reportsQ.error} retry={() => reportsQ.refetch()} />}

      {reportsQ.data && (
        <div className="app-list">
          {reportsQ.data.items.map((r) => (
            <article key={r.id} className="card app-row">
              <div className="app-row-main">
                <h3>
                  {r.category.replaceAll("_", " ")}{" "}
                  <span className="muted small">· {r.target_type.toLowerCase()}</span>
                </h3>
                <p className="muted small">
                  reported by {r.reporter ?? "unknown"} · {new Date(r.created_at).toLocaleString()}
                </p>
                <p className="cover-note">“{r.description}”</p>
                {r.resolution_notes && (
                  <p className="small muted">Resolution: {r.resolution_notes}</p>
                )}
                {r.reviewed_by && (
                  <p className="small muted">
                    reviewed by {r.reviewed_by}{r.reviewed_at ? ` · ${new Date(r.reviewed_at).toLocaleDateString()}` : ""}
                  </p>
                )}
              </div>
              <div className="app-row-side">
                <span className={`badge ${statusClass(r.status)}`}>{r.status.replaceAll("_", " ")}</span>
                <ReviewPanel r={r} />
              </div>
            </article>
          ))}
          {reportsQ.data.count === 0 && (
            <div className="card center"><p className="muted">No reports match this filter.</p></div>
          )}
          <Pagination count={reportsQ.data.count} page={page} onPage={setPage} />
        </div>
      )}
    </section>
  );
}
