/**
 * Matching API — shapes verified against apps/matching (Phase 7):
 * - /recommendations/ returns ranked {job, match_score, recommendation_score,
 *   match_components, recommendation_reasons} items.
 * - preferences: GET lazily creates; PUT/PATCH with preferred_category_ids
 *   (UUID[]), preferred_job_types/payment_types (choice arrays), payment
 *   bounds (max >= min), maximum_distance_km (0 < x <= 20).
 * - engagements: POST {job_id, kind} with kind VIEWED|SAVED|APPLIED;
 *   duplicates rejected per (student, job, kind).
 */

import { api } from "./client";
import type { JobMatch, Paginated, StudentPreference } from "./types";

export interface RecommendationItem {
  job: import("./types").Job;
  match_score: string;
  recommendation_score: number;
  match_components: {
    skill: string;
    location: string;
    availability: string;
    experience: string;
  };
  recommendation_reasons: string[];
}

export async function listRecommendations(page = 1): Promise<Paginated<RecommendationItem>> {
  const { data } = await api.get<Paginated<RecommendationItem>>("/matching/recommendations/", {
    params: { page },
  });
  return data;
}

export async function listMatches(params?: { job_id?: string; minimum_score?: string }): Promise<JobMatch[]> {
  const { data } = await api.get<JobMatch[]>("/matching/matches/", { params });
  return data;
}

export async function calculateMatch(jobId: string): Promise<JobMatch> {
  const { data } = await api.post<JobMatch>(`/matching/matches/calculate/${jobId}/`);
  return data;
}

export async function getPreference(): Promise<StudentPreference> {
  const { data } = await api.get<StudentPreference>("/matching/preferences/");
  return data;
}

export async function updatePreference(
  patch: Partial<Omit<StudentPreference, "id">>,
): Promise<StudentPreference> {
  const { data } = await api.patch<StudentPreference>("/matching/preferences/", patch);
  return data;
}

export type EngagementKind = "VIEWED" | "SAVED" | "APPLIED";

export async function trackEngagement(jobId: string, kind: EngagementKind): Promise<void> {
  await api.post("/matching/engagements/", { job_id: jobId, kind });
}

export async function deleteEngagement(id: string): Promise<void> {
  await api.delete(`/matching/engagements/${id}/`);
}
