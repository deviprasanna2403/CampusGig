import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listRecommendations, trackEngagement, type EngagementKind } from "../../api/matching";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/jobs/StatusBadge";

export default function Recommendations() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);

  const recsQ = useQuery({
    queryKey: ["recommendations", page],
    queryFn: () => listRecommendations(page),
    placeholderData: keepPreviousData,
  });

  const engageM = useMutation({
    mutationFn: ({ jobId, kind }: { jobId: string; kind: EngagementKind }) => trackEngagement(jobId, kind),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recommendations"] }),
  });

  return (
    <section>
      <h1>Recommended for you</h1>
      <p className="muted">Ranked by skill, campus distance, availability, and your saved preferences.</p>

      {recsQ.isLoading && <div className="page-loading">Scoring jobs for you…</div>}
      {recsQ.isError && <ErrorState error={recsQ.error} retry={() => recsQ.refetch()} />}

      {recsQ.data && (
        <>
          <div className="rec-list">
            {recsQ.data.results.map((r) => (
              <article key={r.job.id} className="card rec-card">
                <div className="rec-score">
                  <span className="stat-num">{Math.round(r.recommendation_score)}</span>
                  <span className="stat-label">match</span>
                </div>
                <div className="rec-main">
                  <div className="job-card-head">
                    <h3>
                      <Link to={`/student/jobs/${r.job.id}`}>{r.job.title}</Link>
                    </h3>
                    <StatusBadge status={r.job.status} />
                  </div>
                  <p className="job-meta">
                    {r.job.category?.name ?? "Uncategorized"} · ₹{r.job.payment_amount}/
                    {r.job.payment_type.replaceAll("_", " ").toLowerCase()}
                  </p>
                  {r.recommendation_reasons.length > 0 && (
                    <p className="rec-reasons">{r.recommendation_reasons.join(" · ")}</p>
                  )}
                  <p className="muted small">
                    skill {Math.round(Number(r.match_components.skill))}% · location{" "}
                    {Math.round(Number(r.match_components.location))}% · availability{" "}
                    {Math.round(Number(r.match_components.availability))}%
                  </p>
                </div>
                <div className="rec-actions">
                  <button
                    className="btn ghost"
                    disabled={engageM.isPending}
                    onClick={() => engageM.mutate({ jobId: r.job.id, kind: "SAVED" })}
                  >
                    Save
                  </button>
                  <Link className="btn primary" to={`/student/jobs/${r.job.id}`}>
                    View
                  </Link>
                </div>
              </article>
            ))}
          </div>
          {recsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">No recommendations yet — complete your profile (campus, skills, availability) and they'll appear.</p>
              <Link className="btn primary" to="/student/profile">Complete profile</Link>
            </div>
          )}
          <Pagination count={recsQ.data.count} page={page} onPage={setPage} />
        </>
      )}
    </section>
  );
}
