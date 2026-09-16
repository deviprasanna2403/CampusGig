/**
 * Notifications API — shapes verified against apps/notifications (Phase 7):
 * - GET /notifications/ with optional ?unread=1; ?page_size supported via
 *   DRF pagination settings.
 * - Mark read: PATCH /notifications/<id>/read/.
 */

import { api } from "./client";
import type { NotificationRow, Paginated } from "./types";

export async function listNotifications(params?: {
  unread?: boolean;
  page?: number;
  page_size?: number;
}): Promise<Paginated<NotificationRow>> {
  const { data } = await api.get<Paginated<NotificationRow>>("/notifications/", {
    params: {
      unread: params?.unread || undefined,
      page: params?.page,
      page_size: params?.page_size,
    },
  });
  return data;
}

export async function markNotificationRead(id: string): Promise<NotificationRow> {
  const { data } = await api.patch<NotificationRow>(`/notifications/${id}/read/`);
  return data;
}
