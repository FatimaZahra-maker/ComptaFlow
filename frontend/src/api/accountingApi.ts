import { apiClient } from "./client";
import type { Ecriture } from "../types/ecriture";
import type { Registre } from "../types/registre";

export async function listEntries(statutValidation?: string): Promise<Ecriture[]> {
  const response = await apiClient.get<Ecriture[]>("/accounting/entries", {
    params: statutValidation ? { statut_validation: statutValidation } : {},
  });
  return response.data;
}

export async function validateEntry(id: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(`/accounting/entries/${id}/validate`);
  return response.data;
}

export async function rejectEntry(id: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(`/accounting/entries/${id}/reject`);
  return response.data;
}

export async function toggleSaisieTopaze(id: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(`/accounting/entries/${id}/saisie`);
  return response.data;
}

// Registre dynamique : soit `mois` (mensuel), soit `trimestre` (1-4,
// trimestriel) -- exclusif l'un de l'autre, voir backend/accounting.py.
export async function getRegistre(params: {
  entreprise_id: string;
  categorie: string;
  annee: number;
  mois?: number;
  trimestre?: number;
}): Promise<Registre> {
  const response = await apiClient.get<Registre>("/accounting/registers", { params });
  return response.data;
}
// Ajoute cette fonction à la fin du fichier :
export async function updateEntry(
  id: string,
  payload: Partial<{
    tiers: string;
    numero_piece: string;
    date_piece: string;
    montant_ht: string;
    taux_tva: string;
    montant_tva: string;
    montant_ttc: string;
  }>
): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(`/accounting/entries/${id}`, payload);
  return response.data;
}
// Ajoute cet import en haut si absent :
import type { TvaAnnuelle } from "../types/registre";

// Ajoute cette fonction à la fin du fichier :
export async function getTvaMensuelle(params: {
  entreprise_id: string;
  annee: number;
}): Promise<TvaAnnuelle> {
  const response = await apiClient.get<TvaAnnuelle>("/accounting/tva-mensuelle", { params });
  return response.data;
}