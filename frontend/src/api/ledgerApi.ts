import { apiClient } from "./client";
import type {
  Balance,
  GrandLivre,
  LedgerRebuildResult,
} from "../types/ledger";

export interface LedgerFilters {
  entreprise_id: string;
  date_debut?: string;
  date_fin?: string;
}

export async function getGrandLivre(
  filters: LedgerFilters & { compte_prefix?: string },
): Promise<GrandLivre> {
  const response = await apiClient.get<GrandLivre>("/accounting/grand-livre", {
    params: filters,
  });
  return response.data;
}

export async function getBalance(filters: LedgerFilters): Promise<Balance> {
  const response = await apiClient.get<Balance>("/accounting/balance", {
    params: filters,
  });
  return response.data;
}

export async function rebuildLedger(
  entrepriseId: string,
): Promise<LedgerRebuildResult> {
  const response = await apiClient.post<LedgerRebuildResult>(
    "/accounting/ledger/rebuild",
    null,
    { params: { entreprise_id: entrepriseId } },
  );
  return response.data;
}
