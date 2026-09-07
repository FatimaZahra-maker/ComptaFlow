import { apiClient } from "./client";
import type { Entreprise } from "../types/entreprise";

export type AvailableEntrepriseModule =
  | "achats" | "ventes" | "banque" | "comptes_bancaires"
  | "ecritures" | "registres" | "ledger" | "balance" | "tva"
  | "cloture" | "cpc" | "bilan" | "controls";

export async function listEntreprises(): Promise<Entreprise[]> {
  const response = await apiClient.get<Entreprise[]>("/entreprises");
  return response.data;
}

export async function listAvailableEntreprises(
  module: AvailableEntrepriseModule,
  exercice?: number,
): Promise<Entreprise[]> {
  const [availableResponse, allResponse] = await Promise.all([
    apiClient.get<Entreprise[]>("/entreprises/available", {
      params: { module, exercice },
    }),
    apiClient.get<Entreprise[]>("/entreprises"),
  ]);

  // Un sélecteur doit permettre d'ouvrir un dossier même si ce module ne
  // contient pas encore de données. Les dossiers techniques créés par l'OCR
  // restent exclus : ils ne sont pas des entreprises gérées par le cabinet.
  const managed = allResponse.data.filter(
    (item) => item.is_active !== false && !item.creee_automatiquement,
  );
  const merged = new Map(managed.map((item) => [item.id, item]));
  for (const item of availableResponse.data) {
    if (item.is_active !== false && !item.creee_automatiquement) {
      // Conserver les compteurs enrichis renvoyés par /available.
      merged.set(item.id, item);
    }
  }
  return [...merged.values()].sort((left, right) => left.nom.localeCompare(right.nom, "fr"));
}

export function chooseAvailableEntreprise(
  entreprises: Entreprise[],
  currentId: string,
  preferredId: string | null = null,
): string {
  if (currentId && entreprises.some((item) => item.id === currentId)) return currentId;
  if (preferredId && entreprises.some((item) => item.id === preferredId)) return preferredId;
  if (entreprises.length === 1) return entreprises[0].id;
  return "";
}
