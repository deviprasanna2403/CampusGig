/**
 * Applications API — shapes verified against apps/applications (Phase 6):
 * - POST /applications/student/ takes { job_id, cover_note } (both optional
 *   note-wise); the backend rejects duplicates with
 *   job_id: ["You have already applied to this job."].
 * - withdraw is PATCH /applications/student/<id>/withdraw/ (UpdateAPIView).
 */

import { api } from "./client";
import type { Application, ApplicationStatus, Paginated } from "./types";

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
