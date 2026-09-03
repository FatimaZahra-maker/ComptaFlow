import { apiClient } from "./client";

import type {
  EntryFilters,
  EntryUpdatePayload,
  Ecriture,
} from "../types/ecriture";
import type {
  AllocationRapprochementInput,
  BankMovementFilters,
  CompteBancaireCreate,
  CompteBancaireEntreprise,
  MouvementBancaire,
  MouvementBancaireListe,
  MouvementBancaireUpdate,
  RapprochementCandidat,
  VirementInterneCandidat,
} from "../types/mouvementBancaire";
import type {
  Registre,
  RegistreOption,
  TvaAnnuelle,
  TvaPeriodesAnnee,
} from "../types/registre";

export async function listEntries(
  filters: EntryFilters = {},
): Promise<Ecriture[]> {
  const response = await apiClient.get<Ecriture[]>("/accounting/entries", {
    params: filters,
  });
  return response.data;
}

export async function getEntry(id: string): Promise<Ecriture> {
  const response = await apiClient.get<Ecriture>(`/accounting/entries/${id}`);
  return response.data;
}

export async function validateEntry(id: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(
    `/accounting/entries/${id}/validate`,
  );
  return response.data;
}

export async function rejectEntry(id: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(
    `/accounting/entries/${id}/reject`,
  );
  return response.data;
}

export async function toggleSaisieTopaze(id: string, saisie?: boolean, referenceLot?: string): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(
    `/accounting/entries/${id}/saisie`,
    saisie === undefined ? undefined : { saisie, reference_lot: referenceLot || null },
  );
  return response.data;
}

export async function updateEntry(
  id: string,
  payload: EntryUpdatePayload,
): Promise<Ecriture> {
  const response = await apiClient.patch<Ecriture>(
    `/accounting/entries/${id}`,
    payload,
  );
  return response.data;
}

export async function listBankMovements(
  filters: BankMovementFilters = {},
): Promise<MouvementBancaireListe[]> {
  const response = await apiClient.get<MouvementBancaireListe[]>(
    "/accounting/bank-movements",
    { params: filters },
  );
  return response.data;
}

export async function getBankMovementCandidates(
  movementId: string,
): Promise<RapprochementCandidat[]> {
  const response = await apiClient.get<RapprochementCandidat[]>(
    `/accounting/bank-movements/${movementId}/candidates`,
  );
  return response.data;
}

export async function reconcileBankMovementAuto(
  movementId: string,
): Promise<MouvementBancaire> {
  const response = await apiClient.post<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/reconcile-auto`,
  );
  return response.data;
}

export async function confirmBankMovementReconciliation(
  movementId: string,
  entryId: string,
): Promise<MouvementBancaire> {
  const response = await apiClient.patch<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/reconcile/${entryId}`,
  );
  return response.data;
}

export async function unlinkBankMovementReconciliation(
  movementId: string,
): Promise<MouvementBancaire> {
  const response = await apiClient.delete<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/reconcile`,
  );
  return response.data;
}


export async function confirmBankMovementAllocations(
  movementId: string,
  allocations: AllocationRapprochementInput[],
): Promise<MouvementBancaire> {
  const response = await apiClient.post<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/allocations`,
    { allocations },
  );
  return response.data;
}

export async function updateBankOperation(
  movementId: string,
  payload: MouvementBancaireUpdate,
): Promise<MouvementBancaire> {
  const response = await apiClient.patch<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/operation`,
    payload,
  );
  return response.data;
}

export async function getInternalTransferCandidates(
  movementId: string,
): Promise<VirementInterneCandidat[]> {
  const response = await apiClient.get<VirementInterneCandidat[]>(
    `/accounting/bank-movements/${movementId}/internal-transfer-candidates`,
  );
  return response.data;
}

export async function linkInternalTransfer(
  movementId: string,
  otherMovementId: string,
): Promise<MouvementBancaire> {
  const response = await apiClient.patch<MouvementBancaire>(
    `/accounting/bank-movements/${movementId}/internal-transfer/${otherMovementId}`,
  );
  return response.data;
}

export async function listBankAccounts(
  entrepriseId: string,
): Promise<CompteBancaireEntreprise[]> {
  const response = await apiClient.get<CompteBancaireEntreprise[]>(
    "/accounting/bank-accounts",
    { params: { entreprise_id: entrepriseId } },
  );
  return response.data;
}

export async function createBankAccount(
  payload: CompteBancaireCreate,
): Promise<CompteBancaireEntreprise> {
  const response = await apiClient.post<CompteBancaireEntreprise>(
    "/accounting/bank-accounts",
    payload,
  );
  return response.data;
}

export async function deactivateBankAccount(
  accountId: string,
): Promise<CompteBancaireEntreprise> {
  const response = await apiClient.delete<CompteBancaireEntreprise>(
    `/accounting/bank-accounts/${accountId}`,
  );
  return response.data;
}

export async function getRegistreOptions(): Promise<RegistreOption[]> {
  const response = await apiClient.get<RegistreOption[]>(
    "/accounting/registers/options",
  );
  return response.data;
}

export async function getRegistre(params: {
  entreprise_id: string;
  categorie: string;
  annee: number;
  mois?: number;
  trimestre?: number;
}): Promise<Registre> {
  const response = await apiClient.get<Registre>("/accounting/registers", {
    params,
  });
  return response.data;
}

export async function getTvaMensuelle(params: {
  entreprise_id: string;
  annee: number;
}): Promise<TvaAnnuelle> {
  const response = await apiClient.get<TvaAnnuelle>(
    "/accounting/tva-mensuelle",
    { params },
  );
  return response.data;
}

export async function recalculerTvaV2(params: {
  entreprise_id: string;
  annee: number;
}): Promise<TvaPeriodesAnnee> {
  const response = await apiClient.post<TvaPeriodesAnnee>(
    "/accounting/tva-v2/recalculer",
    null,
    { params },
  );
  return response.data;
}

export async function marquerTvaDeclaree(
  periodId: string,
  entrepriseId: string,
  payload: { date_declaration: string; reference?: string; note?: string },
): Promise<import("../types/registre").TvaPeriodeV2> {
  const response = await apiClient.post<import("../types/registre").TvaPeriodeV2>(
    `/accounting/tva-v2/periodes/${periodId}/declarer`,
    payload,
    { params: { entreprise_id: entrepriseId } },
  );
  return response.data;
}

export async function modifierEcheanceTva(
  periodId: string,
  entrepriseId: string,
  dateLimite: string,
): Promise<import("../types/registre").TvaPeriodeV2> {
  const response = await apiClient.patch<import("../types/registre").TvaPeriodeV2>(
    `/accounting/tva-v2/periodes/${periodId}/echeance`,
    { date_limite: dateLimite },
    { params: { entreprise_id: entrepriseId } },
  );
  return response.data;
}

export async function modifierConfigurationTva(
  entrepriseId: string,
  payload: Partial<import("../types/registre").TvaConfiguration>,
): Promise<import("../types/registre").TvaConfiguration> {
  const response = await apiClient.put<import("../types/registre").TvaConfiguration>(
    `/accounting/tva-v2/configuration/${entrepriseId}`,
    payload,
  );
  return response.data;
}

export async function marquerCentralisationTvaTopaze(
  periodId: string,
  entrepriseId: string,
  saisie: boolean,
  referenceLot?: string,
): Promise<import("../types/registre").TvaPeriodeV2> {
  const response = await apiClient.patch<import("../types/registre").TvaPeriodeV2>(
    `/accounting/tva-v2/periodes/${periodId}/saisie-topaze`,
    { saisie, reference_lot: referenceLot },
    { params: { entreprise_id: entrepriseId } },
  );
  return response.data;
}
