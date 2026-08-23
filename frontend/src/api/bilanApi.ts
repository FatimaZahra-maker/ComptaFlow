import { apiClient } from "./client";
import type { Bilan } from "../types/bilan";

export async function getBilan(params: {
  entreprise_id: string;
  annee: number;
}): Promise<Bilan> {
  const response = await apiClient.get<Bilan>("/accounting/bilan-v2", {
    params: { entreprise_id: params.entreprise_id, exercice: params.annee },
  });
  return response.data;
}
