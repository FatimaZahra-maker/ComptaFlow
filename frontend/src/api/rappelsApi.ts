// Appel API pour les alertes automatiques de la page Rappels & Tâches
// (GET /rappels/alertes, voir backend/app/api/rappels.py).
import { apiClient } from "./client";
import type { AlertesRappels } from "../types/rappel";

export async function getAlertesRappels(): Promise<AlertesRappels> {
  const response = await apiClient.get<AlertesRappels>("/rappels/alertes");
  return response.data;
}