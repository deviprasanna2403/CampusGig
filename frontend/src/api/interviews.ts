/**
 * Interviews API — shapes verified against apps/interviews (Phase 7):
 * - POST {application_id, starts_at, ends_at, timezone_name?, meeting_url?,
 *   notes?}; starts_at must be future, ends after starts; application must
 *   be SHORTLISTED or INTERVIEW stage; both parties see the row.
 * - PATCH can change schedule fields and status (SCHEDULED -> CONFIRMED /
 *   DECLINED / COMPLETED / CANCELLED); updates notify the counterpart.
 */

import { api } from "./client";
import type { Interview, InterviewStatus, Paginated } from "./types";

export async function listInterviews(params?: { page?: number }): Promise<Paginated<Interview>> {
  const { data } = await api.get<Paginated<Interview>>("/interviews/", { params });
  return data;
}

export async function createInterview(input: {
  application_id: string;
  starts_at: string;
  ends_at: string;
  timezone_name?: string;
  meeting_url?: string;
  notes?: string;
}): Promise<Interview> {
  const { data } = await api.post<Interview>("/interviews/", input);
  return data;
}

export async function updateInterview(
  id: string,
  patch: Partial<{
    starts_at: string;
    ends_at: string;
    timezone_name: string | null;
    meeting_url: string;
    notes: string;
    status: InterviewStatus;
  }>,
): Promise<Interview> {
  const { data } = await api.patch<Interview>(`/interviews/${id}/`, patch);
  return data;
}
