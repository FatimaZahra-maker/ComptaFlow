import { apiClient } from "./client";
import type { ExpectedDocument, WorkPeriod } from "../types/workflowComptable";

export async function listWorkPeriods(entrepriseId: string, exercice: number): Promise<WorkPeriod[]> {
  const response = await apiClient.get<WorkPeriod[]>("/accounting/workflow/periodes", { params: { entreprise_id: entrepriseId, exercice } });
  return response.data;
}

export async function lockWorkPeriod(entrepriseId: string, payload: { exercice: number; periode_debut: string; periode_fin: string; date_limite_saisie_topaze?: string }): Promise<WorkPeriod> {
  const response = await apiClient.post<WorkPeriod>("/accounting/workflow/periodes/verrouiller", payload, { params: { entreprise_id: entrepriseId } });
  return response.data;
}

export async function reopenWorkPeriod(entrepriseId: string, periodId: string, justification: string): Promise<WorkPeriod> {
  const response = await apiClient.post<WorkPeriod>(`/accounting/workflow/periodes/${periodId}/reouvrir`, { justification }, { params: { entreprise_id: entrepriseId } });
  return response.data;
}

export async function listExpectedDocuments(entrepriseId: string, exercice: number): Promise<ExpectedDocument[]> {
  const response = await apiClient.get<ExpectedDocument[]>("/accounting/workflow/documents-attendus", { params: { entreprise_id: entrepriseId, exercice } });
  return response.data;
}

export async function createExpectedDocument(entrepriseId: string, payload: {
  type_document: string; frequence: string; periode_debut: string; periode_fin: string;
  date_limite_reception: string; nombre_attendu?: number;
}): Promise<ExpectedDocument> {
  const response = await apiClient.post<ExpectedDocument>("/accounting/workflow/documents-attendus", payload, { params: { entreprise_id: entrepriseId } });
  return response.data;
}

export async function markExpectedDocumentComplete(entrepriseId: string, itemId: string): Promise<ExpectedDocument> {
  const response = await apiClient.patch<ExpectedDocument>(`/accounting/workflow/documents-attendus/${itemId}/completer`, null, { params: { entreprise_id: entrepriseId } });
  return response.data;
}
