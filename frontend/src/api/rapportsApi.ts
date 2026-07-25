import { apiClient } from "./client";
import type { Rapport } from "../types/rapport";

// Récupère le rapport de synthèse pour affichage à l'écran.
export async function getRapport(params: { entreprise_id: string; annee: number; mois?: number }): Promise<Rapport> {
  const response = await apiClient.get<Rapport>("/rapports", { params });
  return response.data;
}

// Construit l'URL de téléchargement du PDF (utilisée dans un <a href>,
// token en query param -- même principe que les autres exports).
export function getRapportPdfUrl(params: { entreprise_id: string; annee: number; mois?: number }): string {
  const token = localStorage.getItem("comptaflow_token");
  const query = new URLSearchParams({
    entreprise_id: params.entreprise_id,
    annee: String(params.annee),
    ...(params.mois ? { mois: String(params.mois) } : {}),
    token: token ?? "",
  });
  return `http://localhost:8000/rapports/pdf?${query.toString()}`;
}