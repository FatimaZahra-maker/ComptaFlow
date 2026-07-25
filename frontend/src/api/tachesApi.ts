import { apiClient } from "./client";
import type { Tache, TacheCreatePayload } from "../types/tache";

export async function listTaches(filters: { entreprise_id?: string; statut?: string; seulement_en_retard?: boolean } = {}): Promise<Tache[]> {
  const response = await apiClient.get<Tache[]>("/taches", { params: filters });
  return response.data;
}

export async function createTache(payload: TacheCreatePayload): Promise<Tache> {
  const response = await apiClient.post<Tache>("/taches", payload);
  return response.data;
}

export async function terminerTache(id: string): Promise<Tache> {
  const response = await apiClient.patch<Tache>(`/taches/${id}/terminer`);
  return response.data;
}

export async function deleteTache(id: string): Promise<void> {
  await apiClient.delete(`/taches/${id}`);
}