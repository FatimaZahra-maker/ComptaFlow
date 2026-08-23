import { apiClient } from "./client";
import type { RegularisationCloture, RegularisationClotureCreate } from "../types/cloture";

export async function listRegularisationsCloture(entrepriseId: string, exercice: number) {
  const response = await apiClient.get<RegularisationCloture[]>("/accounting/cloture", {
    params: { entreprise_id: entrepriseId, exercice },
  });
  return response.data;
}

export async function createRegularisationCloture(entrepriseId: string, payload: RegularisationClotureCreate) {
  const response = await apiClient.post<RegularisationCloture>("/accounting/cloture", payload, {
    params: { entreprise_id: entrepriseId },
  });
  return response.data;
}

export async function validateRegularisationCloture(entrepriseId: string, id: string) {
  const response = await apiClient.post<RegularisationCloture>(`/accounting/cloture/${id}/valider`, null, {
    params: { entreprise_id: entrepriseId },
  });
  return response.data;
}

export async function generateRegularisationCloture(entrepriseId: string, id: string) {
  const response = await apiClient.post<RegularisationCloture>(`/accounting/cloture/${id}/generer`, null, {
    params: { entreprise_id: entrepriseId },
  });
  return response.data;
}

