import { apiClient } from "./client";
import type { CabinetMessage, MessageContact, MessageTaskPayload, PlannedMessageTask } from "../types/message";

export async function requestAccessRenewal(email: string, message?: string): Promise<string> {
  const response = await apiClient.post<{ message: string }>("/messages/access-request", { email, message });
  return response.data.message;
}

export async function listMessageContacts(): Promise<MessageContact[]> {
  const response = await apiClient.get<MessageContact[]>("/messages/contacts");
  return response.data;
}

export async function getUnreadMessageCount(): Promise<number> {
  const response = await apiClient.get<{ count: number }>("/messages/unread-count");
  return response.data.count;
}

export async function getConversation(contactId: string): Promise<CabinetMessage[]> {
  const response = await apiClient.get<CabinetMessage[]>(`/messages/${contactId}`);
  return response.data;
}

export async function sendCabinetMessage(recipientId: string, contenu: string): Promise<CabinetMessage> {
  const response = await apiClient.post<CabinetMessage>("/messages", { recipient_id: recipientId, contenu });
  return response.data;
}

export async function planMessageAsTask(messageId: string, payload: MessageTaskPayload): Promise<PlannedMessageTask> {
  const response = await apiClient.post<PlannedMessageTask>(`/messages/${messageId}/task`, payload);
  return response.data;
}
