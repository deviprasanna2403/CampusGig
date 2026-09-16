/**
 * Admin console APIs (Phase F5) — shapes verified against disk:
 * - core: GET /core/audit/logs/ (admin-only, filters: action, target_type,
 *   target_id, actor, from/to; PageNumberPagination envelope), and
 *   GET /core/analytics/admin/ (window/interval params).
 * - safety: GET /safety/admin/verifications/ + review/revoke actions
 *   (review enforces SUBMITTED -> UNDER_REVIEW -> VERIFIED/REJECTED via
 *   VerificationService; revoke requires notes), and
 *   GET /safety/reports/ (admins see all) + PATCH /safety/admin/reports/{id}/review/.
 * All write actions audit themselves server-side (AuditService).
 */

import { api, getPaginated } from "./client";
import type { AdminAnalytics, AuditLog, BusinessVerification, Report, ReportStatus } from "./types";

/* --- analytics ------------------------------------------------------------ */

export interface AdminAnalyticsQuery {
  from?: string;
  to?: string;
  interval?: "day" | "week" | "month";
}

export async function getAdminAnalytics(query: AdminAnalyticsQuery = {}): Promise<AdminAnalytics> {
  const { data } = await api.get<AdminAnalytics>("/analytics/admin/", { params: query });
  return data;
}

/* --- audit log viewer ------------------------------------------------------ */

export type AuditLogQuery = {
  action?: string;
  target_type?: string;
  target_id?: string;
  actor?: string;
  from?: string;
  to?: string;
  page?: number;
};

export function listAuditLogs(query: AuditLogQuery = {}) {
  return getPaginated<AuditLog>("/audit/logs/", { ...query });
}

/* --- verification review queue --------------------------------------------- */

export function listAllVerifications() {
  return getPaginated<BusinessVerification>("/safety/admin/verifications/");
}

export interface VerificationReviewInput {
  status: "UNDER_REVIEW" | "VERIFIED" | "REJECTED";
  review_notes?: string;
}

export async function reviewVerification(id: string, input: VerificationReviewInput): Promise<BusinessVerification> {
  const { data } = await api.patch<BusinessVerification>(`/safety/admin/verifications/${id}/review/`, input);
  return data;
}

export async function revokeVerification(id: string, review_notes: string): Promise<BusinessVerification> {
  const { data } = await api.patch<BusinessVerification>(`/safety/admin/verifications/${id}/revoke/`, { review_notes });
  return data;
}

/* --- report moderation ------------------------------------------------------ */

export interface ReportQuery {
  status?: ReportStatus;
  page?: number;
}

export function listReports(query: ReportQuery = {}) {
  return getPaginated<Report>("/safety/reports/", { ...query });
}

export interface ReportReviewInput {
  status: ReportStatus;
  resolution_notes?: string;
}

export async function reviewReport(id: string, input: ReportReviewInput): Promise<Report> {
  const { data } = await api.patch<Report>(`/safety/admin/reports/${id}/review/`, input);
  return data;
}
