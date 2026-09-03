export interface GrandLivreLigne {
  id: string;
  date_ecriture: string;
  journal: string;
  numero_piece: string | null;
  compte: string;
  libelle: string;
  debit: string;
  credit: string;
  solde_cumule: string;
  origine: string;
  ecriture_id: string | null;
  mouvement_bancaire_id: string | null;
  regularisation_cloture_id: string | null;
  tva_periode_id: string | null;
  document_id: string | null;
  tiers: string | null;
  statut_topaze: string | null;
}

export interface GrandLivreCompte {
  compte: string;
  libelle_compte: string | null;
  solde_initial: string;
  total_debit: string;
  total_credit: string;
  solde_final: string;
  solde_debiteur: string;
  solde_crediteur: string;
  lignes: GrandLivreLigne[];
}

export interface GrandLivre {
  entreprise_id: string;
  date_debut: string | null;
  date_fin: string | null;
  nombre_comptes: number;
  nombre_lignes: number;
  total_debit: string;
  total_credit: string;
  equilibre: boolean;
  comptes: GrandLivreCompte[];
}

export interface BalanceLigne {
  compte: string;
  libelle_compte: string | null;
  total_debit: string;
  total_credit: string;
  solde_debiteur: string;
  solde_crediteur: string;
}

export interface Balance {
  entreprise_id: string;
  date_debut: string | null;
  date_fin: string | null;
  nombre_comptes: number;
  total_debit: string;
  total_credit: string;
  total_solde_debiteur: string;
  total_solde_crediteur: string;
  equilibree: boolean;
  ecart: string;
  tolerance: string;
  comptes_inconnus: number;
  ecritures_non_saisies_topaze: number;
  anomalies: string[];
  lignes: BalanceLigne[];
}

export interface LedgerRebuildResult {
  entreprise_id: string;
  ecritures_total: number;
  ecritures_completes: number;
  ecritures_incompletes: number;
  mouvements_total: number;
  mouvements_complets: number;
  mouvements_incomplets: number;
  lignes_total: number;
}
