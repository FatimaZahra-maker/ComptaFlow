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
  const response = await apiClient.get<Entreprise[]>("/entreprises/available", {
    params: { module, exercice },
  });
  return response.data;
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
