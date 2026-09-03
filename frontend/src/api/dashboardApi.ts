// Appel API pour récupérer les indicateurs du tableau de bord
// (GET /dashboard, voir backend/app/api/dashboard.py).
import { apiClient } from "./client";
import type { Dashboard } from "../types/dashboard";

export async function getDashboard(period?: string, entrepriseId?: string | null): Promise<Dashboard> {
  // On passe "period" dans l'objet "params" de configuration.
  // Axios va automatiquement transformer cela en /dashboard?period=2026-07
  const response = await apiClient.get<Dashboard>("/dashboard", {
    params: {
      ...(period ? { period } : {}),
      ...(entrepriseId ? { entreprise_id: entrepriseId } : {}),
    }
  });
  
  return response.data;
}
