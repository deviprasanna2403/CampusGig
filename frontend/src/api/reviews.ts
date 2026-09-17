/**
 * Reviews API — Phase 8 backend, F6 UI.
 *
 * Endpoints (apps/safety/urls.py):
 * - GET  /safety/reviews/<user_id>/  → published reviews received by that user
 * - POST /safety/reviews/<user_id>/  → leave a review on a completed engagement
 *
 * POST body: { application: "<uuid>", rating: 1..5, comment?: string }.
 * The backend derives the reviewee from the application (must be the other
 * party), enforces a completed engagement (application SELECTED + job
 * CLOSED/EXPIRED), and rejects duplicates per (application, reviewer).
 */

import { api } from "./client";
import type { JobStatus, Paginated, ReviewRow } from "./types";

/** Job statuses that count as a completed engagement (mirrors ReviewSerializer). */
export const COMPLETED_JOB_STATUSES: JobStatus[] = ["CLOSED", "EXPIRED"];

export function canReview(app: { status: string; job_status?: JobStatus }): boolean {
  return app.status === "SELECTED" && !!app.job_status && COMPLETED_JOB_STATUSES.includes(app.job_status);
}

/** Reviews a user has received (PUBLISHED only, newest first). */
export async function listReviewsForUser(userId: string): Promise<Paginated<ReviewRow>> {
  const { data } = await api.get<Paginated<ReviewRow>>(`/safety/reviews/${userId}/`);
  return data;
}

/** Leave a review on a completed engagement; userId is the counterparty's. */
export async function createReview(input: {
  userId: string;
  application: string;
  rating: number;
  comment?: string;
}): Promise<ReviewRow> {
  const { data } = await api.post<ReviewRow>(`/safety/reviews/${input.userId}/`, {
    application: input.application,
    rating: input.rating,
    comment: input.comment?.trim() ? input.comment.trim() : "",
  });
  return data;
}
