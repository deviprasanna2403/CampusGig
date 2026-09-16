/**
 * Profiles API — shapes verified against apps/profiles (Phase 4):
 * - GET/PATCH /profiles/students/me/ (campus_id write-only UUID; skills +
 *   availability embedded read-only; completion_percentage computed).
 * - Skills: POST /profiles/students/me/skills/ {skill_id, proficiency,
 *   years_of_experience}; DELETE .../skills/<id>/ (no PUT).
 * - Availability: POST .../availability/ {day_of_week, start_time,
 *   end_time}; PATCH/DELETE .../availability/<id>/.
 */

import { api, getPaginated } from "./client";
import type { AvailabilityRow, Campus, Paginated, Skill, StudentProfileFull, StudentSkillRow } from "./types";

export async function getMyStudentProfile(): Promise<StudentProfileFull> {
  const { data } = await api.get<StudentProfileFull>("/profiles/students/me/");
  return data;
}

export async function updateMyStudentProfile(
  patch: Partial<Pick<StudentProfileFull, "full_name" | "campus_id" | "year_of_study" | "bio" | "resume_headline">>,
): Promise<StudentProfileFull> {
  const { data } = await api.patch<StudentProfileFull>("/profiles/students/me/", patch);
  return data;
}

export async function listCampuses(): Promise<Campus[]> {
  // Campus list is paginated; campuses are few — fetch a large page.
  const { data } = await api.get<Paginated<Campus>>("/profiles/campuses/", {
    params: { page_size: 200 },
  });
  return data.results;
}

export async function listSkills(): Promise<Skill[]> {
  const { data } = await api.get<Paginated<Skill>>("/profiles/skills/", {
    params: { page_size: 500 },
  });
  return data.results;
}

export async function addStudentSkill(input: {
  skill_id: string;
  proficiency: string;
  years_of_experience?: number | null;
}): Promise<StudentSkillRow> {
  const { data } = await api.post<StudentSkillRow>("/profiles/students/me/skills/", input);
  return data;
}

export async function deleteStudentSkill(id: string): Promise<void> {
  await api.delete(`/profiles/students/me/skills/${id}/`);
}

export async function addAvailability(input: {
  day_of_week: number;
  start_time: string;
  end_time: string;
}): Promise<AvailabilityRow> {
  const { data } = await api.post<AvailabilityRow>("/profiles/students/me/availability/", input);
  return data;
}

export async function deleteAvailability(id: string): Promise<void> {
  await api.delete(`/profiles/students/me/availability/${id}/`);
}

export { getPaginated };
