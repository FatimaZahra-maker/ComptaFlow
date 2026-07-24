import { apiClient } from "./client";
import type { Document } from "../types/document";

const API_BASE_URL = "http://localhost:8000";

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<Document>("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function listDocuments(): Promise<Document[]> {
  const response = await apiClient.get<Document[]>("/documents");
  return response.data;
}

export function getDocumentFileUrl(documentId: string): string {
  const token = localStorage.getItem("comptaflow_token");
  return `${API_BASE_URL}/documents/${documentId}/fichier?token=${token}`;
}

// Relance le pipeline complet (OCR + extraction + comptabilisation)
// sur un document déjà uploadé -- bouton "Retraiter".
export async function retraiterDocument(documentId: string): Promise<Document> {
  const response = await apiClient.post<Document>(`/documents/${documentId}/retraiter`);
  return response.data;
}