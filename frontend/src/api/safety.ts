/**
 * Safety API — business verification (Phase 8/9A), shapes verified against
 * apps/safety:
 * - GET /safety/verification/ lazily creates the row as SUBMITTED.
 * - PATCH is the submission act while SUBMITTED (details editable);
 *   UNDER_REVIEW/VERIFIED/REVOKED are locked; REJECTED may resubmit.
 * - evidence is a JSON dict (e.g. {registration_cert: url}).
 * - The two-step admin flow (SUBMITTED -> UNDER_REVIEW -> VERIFIED) is
 *   enforced server-side; the UI only displays status.
 */

import { api } from "./client";
import type { BusinessVerification, Report, ReportTargetType } from "./types";

export async function getMyVerification(): Promise<BusinessVerification> {
  const { data } = await api.get<BusinessVerification>("/safety/verification/");
  return data;
}

export async function submitVerification(patch: {
  legal_name?: string;
  registration_reference?: string;
  evidence?: Record<string, string>;
}): Promise<BusinessVerification> {
  const { data } = await api.patch<BusinessVerification>("/safety/verification/", patch);
  return data;
}

/* --- reports (Phase 8 API, F6 student reporting) ----------------------------
 * POST /safety/reports/ — description needs ≥10 chars (server-validated);
 * duplicates of the same target by the same reporter are rejected.
 */

export type ReportCategory =
  | "FAKE_JOB"
  | "HARASSMENT"
  | "PAYMENT_ISSUE"
  | "FAKE_BUSINESS"
  | "INAPPROPRIATE_CONTENT"
  | "OTHER";

export async function createReport(input: {
  target_type: ReportTargetType;
  target_id: string;
  category: ReportCategory;
  description: string;
}): Promise<Report> {
  const { data } = await api.post<Report>("/safety/reports/", input);
  return data;
}

/** Reports the current user has filed (used for "already reported" state). */
export async function listMyReports(params?: { page?: number }): Promise<{ count: number; results: Report[] }> {
  const { data } = await api.get<{ count: number; results: Report[] }>("/safety/reports/", { params });
  return data;
}
