import { apiClient } from "./client";
import type { Cabinet, CabinetUpdatePayload, SystemInfo } from "../types/cabinet";

// Récupère les informations du cabinet de l'utilisateur connecté.
export async function getCabinet(): Promise<Cabinet> {
  const response = await apiClient.get<Cabinet>("/cabinet");
  return response.data;
}

// Modifie les informations du cabinet (réservé aux admins côté backend).
export async function updateCabinet(payload: CabinetUpdatePayload): Promise<Cabinet> {
  const response = await apiClient.patch<Cabinet>("/cabinet", payload);
  return response.data;
}

// Récupère la configuration IA active (cloud/local), en lecture seule.
export async function getSystemInfo(): Promise<SystemInfo> {
  const response = await apiClient.get<SystemInfo>("/system/info");
  return response.data;
}