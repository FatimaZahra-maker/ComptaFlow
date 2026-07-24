// Appel API pour récupérer les indicateurs du tableau de bord
// (GET /dashboard, voir backend/app/api/dashboard.py).
import { apiClient } from "./client";
import type { Dashboard } from "../types/dashboard";

export async function getDashboard(): Promise<Dashboard> {
  const response = await apiClient.get<Dashboard>("/dashboard");
  return response.data;
}