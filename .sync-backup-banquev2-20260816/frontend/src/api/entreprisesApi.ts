import { apiClient } from "./client";

import type { Entreprise } from "../types/entreprise";


export async function listEntreprises(): Promise<Entreprise[]> {
  const response = await apiClient.get<Entreprise[]>(
    "/entreprises"
  );

  return response.data;
}


export async function createEntreprise(
  nom: string,
): Promise<Entreprise> {

  const response = await apiClient.post<Entreprise>(
    "/entreprises",
    {
      nom,
    },
  );

  return response.data;
}