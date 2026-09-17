/**
 * Review moderation (Phase F6) — admin view of every review in any status
 * (GET /safety/admin/reviews/) with hide/restore via
 * PATCH /safety/admin/reviews/{id}/status/ (notes required; audited
 * server-side as review.moderate).
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listAllReviews, setReviewStatus } from "../../api/admin";
import type { ReviewStatus } from "../../api/types";
import { Stars } from "../../components/reviews/ReviewsList";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

const STATUS_OPTIONS: [ReviewStatus | "", string][] = [
  ["", "All statuses"],
  ["PUBLISHED", "Published"],
  ["HIDDEN", "Hidden"],
  ["UNDER_REVIEW", "Under review"],
];

function ModerationPanel({ id, status }: { id: string; status: ReviewStatus }) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: (target: "HIDDEN" | "PUBLISHED") => setReviewStatus(id, target, notes.trim()),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin-reviews"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Moderation failed."),
  });

  return (
    <div className="review-actions">
      {error && <p className="form-error">{error}</p>}
      <input
        type="text"
        placeholder="Moderation notes (required)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      <div className="action-row">
        {status !== "HIDDEN" && (
          <button className="btn danger" disabled={m.isPending || !notes.trim()} onClick={() => m.mutate("HIDDEN")}>
            Hide
          </button>
        )}
        {status !== "PUBLISHED" && (
          <button className="btn ghost" disabled={m.isPending || !notes.trim()} onClick={() => m.mutate("PUBLISHED")}>
            Restore
          </button>
        )}
      </div>
    </div>
  );
}

export default function ReviewModeration() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const reviewsQ = useQuery({
    queryKey: ["admin-reviews", status, page],
    queryFn: () => listAllReviews({ status: (status || undefined) as ReviewStatus | undefined, page }),
    placeholderData: keepPreviousData,
  });

  return (
    <section>
      <div className="list-head">
        <h1>Review moderation</h1>
        <label className="inline-select">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            {STATUS_OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
      </div>

      {reviewsQ.isLoading && <div className="page-loading">Loading reviews…</div>}
      {reviewsQ.isError && <ErrorState error={reviewsQ.error} retry={() => reviewsQ.refetch()} />}

      {reviewsQ.data && (
        <div className="app-list">
          {reviewsQ.data.items.map((r) => (
            <article key={r.id} className="card app-row">
              <div className="app-row-main">
                <h3>
                  <Stars value={r.rating} />
                  <span className="muted small"> · {r.status.replaceAll("_", " ").toLowerCase()}</span>
                </h3>
                <p className="muted small">
                  {r.reviewer_email || r.reviewer} → {r.reviewee_email || r.reviewee} ·{" "}
                  {new Date(r.created_at).toLocaleDateString()}
                </p>
                {r.comment && <p className="cover-note">“{r.comment}”</p>}
              </div>
              <div className="app-row-side">
                <ModerationPanel id={r.id} status={r.status} />
              </div>
            </article>
          ))}
          {reviewsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">No reviews match this filter.</p>
              <p className="muted small">
                Reviews appear here once engagements complete — see{" "}
                <Link to="/admin/verifications">verifications</Link> for the review queue.
              </p>
            </div>
          )}
          <Pagination count={reviewsQ.data.count} page={page} onPage={setPage} />
        </div>
      )}
    </section>
  );
}
