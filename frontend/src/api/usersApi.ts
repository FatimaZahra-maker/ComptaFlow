import { apiClient } from "./client";
import type { UserAdmin, UserCreatePayload } from "../types/user";

export async function listUsers(): Promise<UserAdmin[]> {
  const response = await apiClient.get<UserAdmin[]>("/users");
  return response.data;
}

export async function createUser(payload: UserCreatePayload): Promise<UserAdmin> {
  const response = await apiClient.post<UserAdmin>("/users", payload);
  return response.data;
}

export async function deactivateUser(id: string): Promise<UserAdmin> {
  const response = await apiClient.patch<UserAdmin>(`/users/${id}/deactivate`);
  return response.data;
}