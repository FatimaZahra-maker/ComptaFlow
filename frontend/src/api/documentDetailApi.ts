// Appel API pour récupérer le détail complet d'un document
// (GET /documents/{id}, voir backend/app/api/documents.py).
import { apiClient } from "./client";
import type { DocumentDetail } from "../types/documentDetail";

export async function getDocumentDetail(id: string): Promise<DocumentDetail> {
  const response = await apiClient.get<DocumentDetail>(`/documents/${id}`);
  return response.data;
}