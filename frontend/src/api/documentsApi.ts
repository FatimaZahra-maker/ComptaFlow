import { apiClient, fetchApiBlob } from "./client";

import type { Document } from "../types/document";
import type { DocumentDetail } from "../types/documentDetail";
import type {
  MouvementBancaire,
  MouvementBancaireUpdate,
} from "../types/mouvementBancaire";

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<Document>(
    "/documents/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );

  return response.data;
}

export async function auditUploadBatch(documentIds: string[]): Promise<void> {
  if (documentIds.length < 2) return;
  await apiClient.post("/documents/upload/batch-audit", { document_ids: documentIds });
}

export async function listDocuments(): Promise<Document[]> {
  const response = await apiClient.get<Document[]>("/documents");
  return response.data;
}

export function fetchDocumentFile(documentId: string): Promise<Blob> {
  return fetchApiBlob(`/documents/${documentId}/fichier`);
}

export async function openDocumentFile(documentId: string): Promise<void> {
  const blob = await fetchDocumentFile(documentId);
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

export async function retraiterDocument(documentId: string): Promise<Document> {
  const response = await apiClient.post<Document>(
    `/documents/${documentId}/retraiter`,
  );
  return response.data;
}

export async function assignDocumentEntreprise(documentId: string, entrepriseId: string): Promise<DocumentDetail> {
  const response = await apiClient.patch<DocumentDetail>(`/documents/${documentId}/entreprise`, {
    entreprise_id: entrepriseId,
  });
  return response.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}

export async function toggleDocumentSaisie(
  documentId: string,
): Promise<{ document_id: string; saisie_topaze: boolean }> {
  const response = await apiClient.patch<{
    document_id: string;
    saisie_topaze: boolean;
  }>(`/documents/${documentId}/saisie`);
  return response.data;
}

export async function validateDocument(
  documentId: string,
): Promise<DocumentDetail> {
  const response = await apiClient.patch<DocumentDetail>(
    `/documents/${documentId}/validate`,
  );
  return response.data;
}

export async function rejectDocument(
  documentId: string,
): Promise<DocumentDetail> {
  const response = await apiClient.patch<DocumentDetail>(
    `/documents/${documentId}/reject`,
  );
  return response.data;
}

export async function updateBankMovement(
  documentId: string,
  movementId: string,
  payload: MouvementBancaireUpdate,
): Promise<MouvementBancaire> {
  const response = await apiClient.patch<MouvementBancaire>(
    `/documents/${documentId}/mouvements/${movementId}`,
    payload,
  );
  return response.data;
}

function safeBaseName(fileName: string): string {
  const withoutExtension = fileName.replace(/\.[^/.]+$/, "");
  return withoutExtension.replace(/[^a-zA-Z0-9_-]+/g, "_") || "document";
}

export async function downloadDocumentData(
  documentId: string,
  format: "csv" | "xlsx",
  originalFileName: string,
): Promise<void> {
  const response = await apiClient.get<Blob>(
    `/documents/${documentId}/export/${format}`,
    { responseType: "blob" },
  );

  const objectUrl = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `donnees_extraites_${safeBaseName(originalFileName)}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
