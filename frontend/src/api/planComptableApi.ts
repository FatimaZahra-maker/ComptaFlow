import { apiClient } from "./client";
import type { CompteComptableCreate, CompteComptableEntreprise, TypeUsageCompte } from "../types/planComptable";

export async function listPlanAccounts(entrepriseId: string, typeUsage?: TypeUsageCompte): Promise<CompteComptableEntreprise[]> {
  const response = await apiClient.get<CompteComptableEntreprise[]>(`/entreprises/${entrepriseId}/plan-comptable`, {
    params: typeUsage ? { type_usage: typeUsage } : undefined,
  });
  return response.data;
}

export async function createPlanAccount(entrepriseId: string, payload: CompteComptableCreate): Promise<CompteComptableEntreprise> {
  const response = await apiClient.post<CompteComptableEntreprise>(`/entreprises/${entrepriseId}/plan-comptable`, payload);
  return response.data;
}

export async function deactivatePlanAccount(entrepriseId: string, accountId: string): Promise<void> {
  await apiClient.delete(`/entreprises/${entrepriseId}/plan-comptable/${accountId}`);
}
