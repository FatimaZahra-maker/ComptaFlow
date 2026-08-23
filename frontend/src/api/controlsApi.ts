import { apiClient } from "./client";
import type { PreClotureControls } from "../types/controls";

export async function getPreClotureControls(
  entrepriseId: string,
  exercice: number,
): Promise<PreClotureControls> {
  const response = await apiClient.get<PreClotureControls>(
    `/accounting/controls/${entrepriseId}`,
    { params: { exercice } },
  );
  return response.data;
}
