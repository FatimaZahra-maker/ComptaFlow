export interface ControleGrandLivreBalance {
  total_debit_grand_livre: string;
  total_credit_grand_livre: string;
  total_debit_balance: string;
  total_credit_balance: string;
  coherent: boolean;
  groupes_sources_desequilibres: number;
}

export interface CpcCompteDetail {
  compte: string;
  libelle_compte: string | null;
  rubrique: string;
  debit: string;
  credit: string;
  montant: string;
}

export interface CpcComparaison {
  code: string;
  libelle: string;
  montant_n: string;
  montant_n_1: string | null;
  variation_mad: string | null;
  variation_pct: string | null;
}

export interface Cpc {
  entreprise_id: string;
  exercice: number;
  exercice_precedent: number;
  donnees_n_1_disponibles: boolean;
  rubriques: CpcComparaison[];
  resultats: CpcComparaison[];
  comptes: CpcCompteDetail[];
  comptes_non_classes: CpcCompteDetail[];
  anomalies: string[];
  statut: "ok" | "a_verifier";
  controle_grand_livre_balance: ControleGrandLivreBalance;
  nombre_lignes: number;
  nombre_comptes: number;
  source_calcul: string;
}
