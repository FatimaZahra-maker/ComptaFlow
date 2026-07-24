import { apiClient } from "./client";
import type { NotificationsResponse, NotificationsStats } from "../types/notification";

export async function getNotifications(): Promise<NotificationsResponse> {
  const response = await apiClient.get<NotificationsResponse>("/notifications");
  return response.data;
}

export async function getNotificationsStats(): Promise<NotificationsStats> {
  const response = await apiClient.get<NotificationsStats>("/notifications/stats");
  return response.data;
}