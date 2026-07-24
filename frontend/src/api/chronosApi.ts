import { apiClient } from "./client";
import type { DocumentChrono } from "../types/chrono";

interface ChronoFilters {
  entreprise_id?: string;
  categorie?: string;
  annee?: number;
  mois?: number;
}

export async function listChronoDocuments(filters: ChronoFilters = {}): Promise<DocumentChrono[]> {
  const response = await apiClient.get<DocumentChrono[]>("/chronos/documents", { params: filters });
  return response.data;
}

export async function listAnneesDisponibles(filters: { entreprise_id?: string; categorie?: string } = {}): Promise<number[]> {
  const response = await apiClient.get<number[]>("/chronos/annees", { params: filters });
  return response.data;
}