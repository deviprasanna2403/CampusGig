import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createReview } from "../../api/reviews";
import { ApiError } from "../../api/client";

const RATING_LABELS: Record<number, string> = {
  1: "1 — poor",
  2: "2 — below average",
  3: "3 — okay",
  4: "4 — good",
  5: "5 — excellent",
};

/**
 * Write a review for a completed engagement (POST /safety/reviews/<userId>/).
 * The backend enforces that the application is SELECTED on a CLOSED/EXPIRED
 * job and that this reviewer hasn't already reviewed it.
 */
export default function ReviewForm({
  userId,
  applicationId,
  counterpartyLabel,
  onDone,
  onCancel,
}: {
  userId: string;
  applicationId: string;
  counterpartyLabel: string;
  onDone?: () => void;
  onCancel?: () => void;
}) {
  const queryClient = useQueryClient();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () =>
      createReview({
        userId,
        application: applicationId,
        rating,
        comment,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      queryClient.invalidateQueries({ queryKey: ["my-applications"] });
      queryClient.invalidateQueries({ queryKey: ["business-applications"] });
      setError(null);
      onDone?.();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not submit review."),
  });

  return (
    <div className="review-form">
      <h3>Leave a review for {counterpartyLabel}</h3>
      {error && <div className="form-error">{error}</div>}
      <div className="star-picker" role="radiogroup" aria-label="Rating">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={rating === n}
            className={n <= rating ? "star-btn on" : "star-btn"}
            disabled={m.isPending}
            onClick={() => setRating(n)}
          >
            ★
          </button>
        ))}
        {rating > 0 && <span className="muted small">{RATING_LABELS[rating]}</span>}
      </div>
      <label>
        Comment (optional)
        <textarea
          rows={3}
          maxLength={3000}
          placeholder="How did the engagement go?"
          value={comment}
          disabled={m.isPending}
          onChange={(e) => setComment(e.target.value)}
        />
      </label>
      <div className="action-row">
        <button
          className="btn primary"
          disabled={m.isPending || rating < 1}
          onClick={() => m.mutate()}
        >
          {m.isPending ? "Submitting…" : "Submit review"}
        </button>
        {onCancel && (
          <button className="btn ghost" disabled={m.isPending} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
