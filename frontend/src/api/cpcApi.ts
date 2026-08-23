import { apiClient } from "./client";
import type { Cpc } from "../types/cpc";

export async function getCpc(params: {
  entreprise_id: string;
  annee: number;
}): Promise<Cpc> {
  const response = await apiClient.get<Cpc>("/accounting/cpc-v2", {
    params: { entreprise_id: params.entreprise_id, exercice: params.annee },
  });
  return response.data;
}
