import { apiClient } from "./client";
import type { Entreprise } from "../types/entreprise";

export async function listEntreprises(): Promise<Entreprise[]> {
  const response = await apiClient.get<Entreprise[]>("/entreprises");
  return response.data;
}