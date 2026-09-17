/**
 * Applications API — shapes verified against apps/applications (Phase 6):
 * - POST /applications/student/ takes { job_id, cover_note } (both optional
 *   note-wise); the backend rejects duplicates with
 *   job_id: ["You have already applied to this job."].
 * - withdraw is PATCH /applications/student/<id>/withdraw/ (UpdateAPIView).
 */

import { api } from "./client";
import type { Application, ApplicationStatus, JobStatus, Paginated } from "./types";

export interface ApplicationRow extends Application {
  job_title: string; // `job` is a StringRelatedField -> Job.__str__ = title
}

export async function listMyApplications(params?: {
  status?: ApplicationStatus;
  page?: number;
}): Promise<Paginated<ApplicationRow>> {
  const { data } = await api.get<Paginated<ApplicationRow>>("/applications/student/", { params });
  return data;
}

export async function applyToJob(jobId: string, coverNote: string): Promise<ApplicationRow> {
  const { data } = await api.post<ApplicationRow>("/applications/student/", {
    job_id: jobId,
    cover_note: coverNote,
  });
  return data;
}

export async function withdrawApplication(id: string): Promise<ApplicationRow> {
  const { data } = await api.patch<ApplicationRow>(`/applications/student/${id}/withdraw/`, {});
  return data;
}

/* --- business-side (Phase F3) ---------------------------------------------
 * BusinessApplicationSerializer shape: { id, job (title), student (email),
 * cover_note, status, submitted_at, created_at, updated_at } — no job_id,
 * so per-job filtering is done server-side via the ?job=<uuid> param.
 * Businesses cannot set WITHDRAWN (backend validates this).
 */

export interface BusinessApplicationRow {
  id: string;
  job: string;
  student: string;
  cover_note: string;
  status: ApplicationStatus;
  /** Phase F6 reviews — see Application type for the rationale. */
  job_status?: JobStatus;
  counterparty_id?: string;
  my_review_rating?: number | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

export async function listBusinessApplications(params?: {
  job?: string;
  status?: string;
  page?: number;
}): Promise<Paginated<BusinessApplicationRow>> {
  const { data } = await api.get<Paginated<BusinessApplicationRow>>("/applications/business/", {
    params,
  });
  return data;
}

export async function updateApplicationStatus(
  id: string,
  status: ApplicationStatus,
): Promise<BusinessApplicationRow> {
  const { data } = await api.patch<BusinessApplicationRow>(`/applications/business/${id}/`, {
    status,
  });
  return data;
}
