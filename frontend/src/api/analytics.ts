/**
 * Analytics API — Phase 9B endpoints, response shapes mirrored in types.ts.
 * The backend validates from/to (ISO dates), interval (day|week|month) and
 * rejects from>to with a 400 envelope.
 */

import { api } from "./client";
import type { AdminAnalytics, BusinessAnalytics, StudentAnalytics } from "./types";

export interface AnalyticsQuery {
  from?: string;
  to?: string;
  interval?: "day" | "week" | "month";
}

export async function adminAnalytics(query?: AnalyticsQuery): Promise<AdminAnalytics> {
  const { data } = await api.get<AdminAnalytics>("/analytics/admin/", { params: query });
  return data;
}

export async function businessAnalytics(query?: AnalyticsQuery): Promise<BusinessAnalytics> {
  const { data } = await api.get<BusinessAnalytics>("/analytics/business/me/", { params: query });
  return data;
}

export async function studentAnalytics(query?: AnalyticsQuery): Promise<StudentAnalytics> {
  const { data } = await api.get<StudentAnalytics>("/analytics/student/me/", { params: query });
  return data;
}
