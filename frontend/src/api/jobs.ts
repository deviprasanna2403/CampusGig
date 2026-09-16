/**
 * Jobs API — shapes verified against apps/jobs (Phase 5):
 * - list filters: search, category (name, case-insensitive), job_type,
 *   payment_type, min/max_payment, status, date, skill, sort
 *   (distance|payment|newest|deadline), campus_id (for sort=distance).
 * - nearby/: student-only; campus_id optional when the profile has a
 *   campus; radius_km must be a positive number; results are ordered
 *   nearest-first (distance is used for ordering only — the serializer
 *   does not emit a distance field).
 * - Students only ever see PUBLISHED/OPEN jobs in list/detail.
 */

import { api } from "./client";
import type { Job, JobCategory, Paginated } from "./types";

/** The job serializer has one shape for list and detail — no extra fields. */
export type JobDetail = Job;

export interface JobQuery {
  search?: string;
  category?: string;
  job_type?: string;
  payment_type?: string;
  min_payment?: string;
  max_payment?: string;
  sort?: "distance" | "payment" | "newest" | "deadline";
  campus_id?: string;
  page?: number;
}

export async function listJobs(query: JobQuery): Promise<Paginated<Job>> {
  const { data } = await api.get<Paginated<Job>>("/jobs/jobs/", { params: query });
  return data;
}

export async function nearbyJobs(params: {
  campus_id?: string;
  radius_km?: string;
  page?: number;
}): Promise<Paginated<Job>> {
  const { data } = await api.get<Paginated<Job>>("/jobs/jobs/nearby/", {
    params,
  });
  return data;
}

export async function getJob(id: string): Promise<JobDetail> {
  const { data } = await api.get<JobDetail>(`/jobs/jobs/${id}/`);
  return data;
}

export async function listCategories(): Promise<JobCategory[]> {
  // Categories are paginated by default; pull a large page for the dropdown.
  const { data } = await api.get<Paginated<JobCategory>>("/jobs/categories/", {
    params: { page_size: 100 },
  });
  return data.results;
}
