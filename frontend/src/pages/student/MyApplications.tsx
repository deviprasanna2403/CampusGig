import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listMyApplications, withdrawApplication } from "../../api/applications";
import { canReview } from "../../api/reviews";
import type { ApplicationStatus } from "../../api/types";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/jobs/StatusBadge";
import ReviewForm from "../../components/reviews/ReviewForm";
import { Stars } from "../../components/reviews/ReviewsList";

const STATUS_OPTIONS: [ApplicationStatus | "", string][] = [
  ["", "All statuses"],
  ["SUBMITTED", "Submitted"],
  ["SHORTLISTED", "Shortlisted"],
  ["INTERVIEW", "Interview"],
  ["SELECTED", "Selected"],
  ["REJECTED", "Rejected"],
  ["WITHDRAWN", "Withdrawn"],
];

export default function MyApplications() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<ApplicationStatus | "">("");
  const [page, setPage] = useState(1);

  const appsQ = useQuery({
    queryKey: ["my-applications", status, page],
    queryFn: () => listMyApplications({ status: status || undefined, page }),
    placeholderData: keepPreviousData,
  });

  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const withdrawM = useMutation({
    mutationFn: withdrawApplication,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["my-applications"] }),
  });

  const justApplied = (location.state as { applied?: boolean } | null)?.applied;

  return (
    <section>
      <div className="list-head">
        <h1>My applications</h1>
        <label className="inline-select">
          <select value={status} onChange={(e) => { setStatus(e.target.value as ApplicationStatus | ""); setPage(1); }}>
            {STATUS_OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
      </div>

      {justApplied && (
        <div className="success-note">Application submitted — the business will review it.</div>
      )}

      {withdrawM.isError && (
        <div className="form-error">
          {withdrawM.error instanceof Error ? withdrawM.error.message : "Could not withdraw."}
        </div>
      )}

      {appsQ.isLoading && <div className="page-loading">Loading applications…</div>}
      {appsQ.isError && <ErrorState error={appsQ.error} retry={() => appsQ.refetch()} />}

      {appsQ.data && (
        <>
          <div className="app-list">
            {appsQ.data.results.map((a) => (
              <article key={a.id} className="card app-row">
                <div className="app-row-main">
                  <h3>{a.job}</h3>
                  <p className="muted small">
                    Applied {new Date(a.submitted_at).toLocaleDateString()} · {a.student}
                  </p>
                  {a.cover_note && <p className="cover-note">“{a.cover_note}”</p>}
                </div>
                <div className="app-row-side">
                  <StatusBadge status={a.status} />
                  {a.status === "SUBMITTED" && (
                    <button
                      className="btn ghost"
                      disabled={withdrawM.isPending}
                      onClick={() => withdrawM.mutate(a.id)}
                    >
                      Withdraw
                    </button>
                  )}
                  {canReview(a) && a.my_review_rating != null && (
                    <span className="muted small">You rated: <Stars value={a.my_review_rating} /></span>
                  )}
                  {canReview(a) && a.my_review_rating == null && a.counterparty_id && reviewingId !== a.id && (
                    <button className="btn ghost" onClick={() => setReviewingId(a.id)}>
                      Leave review
                    </button>
                  )}
                  {canReview(a) && a.my_review_rating == null && reviewingId === a.id && a.counterparty_id && (
                    <ReviewForm
                      userId={a.counterparty_id}
                      applicationId={a.id}
                      counterpartyLabel="the business"
                      onDone={() => setReviewingId(null)}
                      onCancel={() => setReviewingId(null)}
                    />
                  )}
                  {a.status === "SELECTED" && !canReview(a) && (
                    <span className="muted small">Review opens when the job completes.</span>
                  )}
                </div>
              </article>
            ))}
          </div>
          {appsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">You haven't applied to any jobs yet.</p>
            </div>
          )}
          <Pagination count={appsQ.data.count} page={page} onPage={setPage} />
        </>
      )}
    </section>
  );
}
