import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listReviewsForUser } from "../../api/reviews";

/** Render 1–5 as ★ characters; hollow past the rating. */
export function Stars({ value }: { value: number }) {
  const n = Math.max(0, Math.min(5, Math.round(value)));
  return (
    <span className="stars" aria-label={`${n} out of 5 stars`}>
      {"★".repeat(n)}
      <span className="stars-empty">{"★".repeat(5 - n)}</span>
    </span>
  );
}

/**
 * Reviews received by a user (PUBLISHED only), with average.
 * Used on dashboards and the job detail page.
 */
export default function ReviewsList({
  userId,
  emptyText = "No reviews yet.",
  max = undefined,
}: {
  userId: string;
  emptyText?: string;
  max?: number;
}) {
  const q = useQuery({
    queryKey: ["reviews", userId],
    queryFn: () => listReviewsForUser(userId),
    staleTime: 60_000,
  });

  if (q.isLoading) return <p className="muted small">Loading reviews…</p>;
  if (q.isError) return <p className="muted small">Could not load reviews.</p>;

  const rows = q.data?.results ?? [];
  const shown = max ? rows.slice(0, max) : rows;

  if (shown.length === 0) return <p className="muted small">{emptyText}</p>;

  const avg = rows.reduce((sum, r) => sum + r.rating, 0) / rows.length;

  return (
    <div className="reviews-block">
      <p className="muted small">
        <Stars value={avg} /> {avg.toFixed(1)} average · {rows.length} review{rows.length === 1 ? "" : "s"}
      </p>
      <ul className="review-list">
        {shown.map((r) => (
          <li key={r.id} className="review-item">
            <div className="review-head">
              <Stars value={r.rating} />
              <span className="muted small">{new Date(r.created_at).toLocaleDateString()}</span>
            </div>
            {r.comment && <p className="review-comment">“{r.comment}”</p>}
            <p className="muted small">— {r.reviewer_email || r.reviewer}</p>
          </li>
        ))}
      </ul>
      {max && rows.length > shown.length && (
        <p className="muted small">
          <Link to={`/reviews/${userId}`}>See all {rows.length} reviews →</Link>
        </p>
      )}
    </div>
  );
}
