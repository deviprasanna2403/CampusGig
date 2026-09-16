/**
 * Verification review queue (Phase F5) — lists every BusinessVerification
 * (GET /safety/admin/verifications/) with the two-step review flow the
 * backend enforces (9A): SUBMITTED -> UNDER_REVIEW -> VERIFIED/REJECTED.
 * REVOKED rows offer a re-review path; revoke requires notes.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listAllVerifications, reviewVerification, revokeVerification } from "../../api/admin";
import type { BusinessVerification, VerificationStatus } from "../../api/types";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

function statusClass(s: VerificationStatus): string {
  if (s === "VERIFIED") return "ok";
  if (s === "REJECTED" || s === "REVOKED") return "danger";
  return "warn";
}

function ActionPanel({ v }: { v: BusinessVerification }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-verifications"] });
    queryClient.invalidateQueries({ queryKey: ["admin-analytics"] });
  };

  const reviewM = useMutation({
    mutationFn: (status: "UNDER_REVIEW" | "VERIFIED" | "REJECTED") =>
      reviewVerification(v.id, { status, review_notes: notes || undefined }),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof Error ? err.message : "Review failed."),
  });

  const revokeM = useMutation({
    mutationFn: () => revokeVerification(v.id, notes),
    onSuccess: () => { setError(null); setRevoking(false); invalidate(); },
    onError: (err) => setError(err instanceof Error ? err.message : "Revoke failed."),
  });

  const busy = reviewM.isPending || revokeM.isPending;

  if (v.status === "VERIFIED" && !revoking) {
    return (
      <div className="review-actions">
        <button className="btn danger" disabled={busy} onClick={() => setRevoking(true)}>Revoke…</button>
      </div>
    );
  }

  const buttons: [string, "UNDER_REVIEW" | "VERIFIED" | "REJECTED", string][] =
    v.status === "SUBMITTED"
      ? [["Start review", "UNDER_REVIEW", "ghost"]]
      : v.status === "UNDER_REVIEW"
        ? [["Verify", "VERIFIED", "primary"], ["Reject", "REJECTED", "danger"]]
        : v.status === "REVOKED"
          ? [["Re-verify", "VERIFIED", "primary"]]
          : [];

  return (
    <div className="review-actions">
      {error && <p className="form-error">{error}</p>}
      {(buttons.length > 0 || revoking) && (
        <input
          type="text"
          placeholder="Review notes (required to revoke)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      )}
      <div className="action-row">
        {buttons.map(([label, status, cls]) => (
          <button
            key={status}
            className={`btn ${cls}`}
            disabled={busy || (status === "VERIFIED" && v.status === "REVOKED" && !notes.trim())}
            onClick={() => reviewM.mutate(status)}
          >
            {label}
          </button>
        ))}
        {revoking && (
          <button
            className="btn danger"
            disabled={busy || !notes.trim()}
            onClick={() => revokeM.mutate()}
          >
            Confirm revoke
          </button>
        )}
      </div>
    </div>
  );
}

export default function VerificationReview() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const verificationsQ = useQuery({
    queryKey: ["admin-verifications", status, page],
    queryFn: () => listAllVerifications(),
    placeholderData: keepPreviousData,
  });

  const rows = (verificationsQ.data?.items ?? []).filter((v) => !status || v.status === status);

  return (
    <section>
      <div className="list-head">
        <h1>Business verification queue</h1>
        <label className="inline-select">
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          >
            <option value="">All statuses</option>
            <option value="SUBMITTED">Submitted</option>
            <option value="UNDER_REVIEW">Under review</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
            <option value="REVOKED">Revoked</option>
          </select>
        </label>
      </div>

      {verificationsQ.isLoading && <div className="page-loading">Loading verifications…</div>}
      {verificationsQ.isError && <ErrorState error={verificationsQ.error} retry={() => verificationsQ.refetch()} />}

      {verificationsQ.data && (
        <div className="app-list">
          {rows.map((v) => (
            <article key={v.id} className="card app-row">
              <div className="app-row-main">
                <h3>{v.legal_name || v.business}</h3>
                <p className="muted small">
                  {v.business} · reg {v.registration_reference || "—"} · submitted {new Date(v.created_at).toLocaleDateString()}
                </p>
                {v.evidence && Object.keys(v.evidence).length > 0 && (
                  <p className="small">
                    Evidence:{" "}
                    {Object.entries(v.evidence).map(([k, url]) => (
                      <a key={k} href={String(url)} target="_blank" rel="noreferrer" className="evidence-link">
                        {k.replaceAll("_", " ")}
                      </a>
                    ))}
                  </p>
                )}
                {v.review_notes && <p className="cover-note">“{v.review_notes}”</p>}
              </div>
              <div className="app-row-side">
                <span className={`badge ${statusClass(v.status)}`}>{v.status.replaceAll("_", " ")}</span>
                <ActionPanel v={v} />
              </div>
            </article>
          ))}
          {rows.length === 0 && (
            <div className="card center"><p className="muted">No verifications match this filter.</p></div>
          )}
          <Pagination count={verificationsQ.data.count} page={page} onPage={setPage} />
        </div>
      )}
    </section>
  );
}
