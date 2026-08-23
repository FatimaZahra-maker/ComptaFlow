import { apiClient, downloadApiBlob } from "./client";
import type { Rapport } from "../types/rapport";

// Récupère le rapport de synthèse pour affichage à l'écran.
export async function getRapport(params: { entreprise_id: string; annee: number; mois?: number }): Promise<Rapport> {
  const response = await apiClient.get<Rapport>("/rapports", { params });
  return response.data;
}

// Construit l'URL de téléchargement du PDF (utilisée dans un <a href>,
// token en query param -- même principe que les autres exports).
export function downloadRapportPdf(params: { entreprise_id: string; annee: number; mois?: number }): Promise<void> {
  const periode = params.mois ? `${params.mois}_${params.annee}` : String(params.annee);
  return downloadApiBlob("/rapports/pdf", `rapport_${periode}.pdf`, params);
}
