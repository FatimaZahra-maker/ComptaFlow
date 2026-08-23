import type { ControleGrandLivreBalance } from "./cpc";

export interface BilanCompteDetail {
  compte: string;
  libelle_compte: string | null;
  rubrique: string;
  cote: string;
  debit: string;
  credit: string;
  solde_debiteur: string;
  solde_crediteur: string;
  montant_bilan: string;
  est_compte_correcteur: boolean;
}

export interface BilanRubrique {
  code: string;
  libelle: string;
  montant: string;
}

export interface ControleResultatBilan {
  resultat_cpc: string;
  resultat_comptabilise: string;
  resultat_non_affecte: string;
  deja_comptabilise: boolean;
  coherent: boolean;
  statut: string;
}

export interface Bilan {
  entreprise_id: string;
  exercice: number;
  date_cloture: string;
  actif: BilanRubrique[];
  passif: BilanRubrique[];
  total_actif: string;
  total_passif: string;
  ecart: string;
  resultat_cpc: string;
  resultat_non_affecte: string;
  resultat_deja_comptabilise: boolean;
  bilan_equilibre: boolean;
  controle_resultat: ControleResultatBilan;
  controle_grand_livre_balance: ControleGrandLivreBalance;
  comptes: BilanCompteDetail[];
  comptes_non_classes: BilanCompteDetail[];
  anomalies: string[];
  statut: "ok" | "a_verifier";
  nombre_lignes: number;
  nombre_comptes: number;
  source_calcul: string;
}
