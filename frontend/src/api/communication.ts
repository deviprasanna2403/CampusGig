/**
 * Communication API — shapes verified against apps/communication (Phase 7):
 * - Conversations exist per application, creatable only by participants and
 *   only once the application is SHORTLISTED/INTERVIEW/SELECTED (one per
 *   application). other_party is the counterpart's email; unread_count is
 *   computed per caller.
 * - Messages: sender is implicit; body must be non-blank. There is no
 *   WebSocket — the UI polls (5s) for new messages.
 * - Read receipts: PATCH /communication/messages/<id>/read/.
 */

import { api } from "./client";
import type { Conversation, Message, Paginated } from "./types";

export async function listConversations(): Promise<Paginated<Conversation>> {
  const { data } = await api.get<Paginated<Conversation>>("/communication/conversations/");
  return data;
}

export async function createConversation(applicationId: string): Promise<Conversation> {
  const { data } = await api.post<Conversation>("/communication/conversations/", {
    application_id: applicationId,
  });
  return data;
}

export async function listMessages(conversationId: string, page = 1): Promise<Paginated<Message>> {
  const { data } = await api.get<Paginated<Message>>(
    `/communication/conversations/${conversationId}/messages/`,
    { params: { page } },
  );
  return data;
}

export async function sendMessage(conversationId: string, body: string): Promise<Message> {
  const { data } = await api.post<Message>(
    `/communication/conversations/${conversationId}/messages/`,
    { body },
  );
  return data;
}

export async function markMessageRead(messageId: string): Promise<Message> {
  const { data } = await api.patch<Message>(`/communication/messages/${messageId}/read/`);
  return data;
}
