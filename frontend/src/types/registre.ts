import type { Ecriture } from "./ecriture";

export interface RegistreOption {
  entreprise_id: string;
  categorie: string;
  annee: number;
  mois: number;
  nombre: number;
}

export interface Registre {
  categorie: string;
  entreprise_id: string;
  annee: number;
  mois: number;
  nombre: number;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  lignes: Ecriture[];
}

export type NatureCompteTva =
  | "collectee"
  | "deductible_charges"
  | "deductible_immobilisations";

export interface TvaCompteDetail {
  compte: string;
  nature: NatureCompteTva | string;
  debit: string;
  credit: string;
  montant_net: string;
}

export interface TvaMensuelle {
  mois: number;
  annee: number;

  tva_collectee: string;
  tva_deductible_charges: string;
  tva_deductible_immobilisations: string;
  tva_deductible: string;
  tva_nette: string;
  tva_a_payer: string;
  credit_tva: string;

  nombre_ecritures: number;
  nombre_lignes_tva: number;
  a_verifier: boolean;
  raisons_verification: string[];
  comptes: TvaCompteDetail[];
}

export interface TvaAnnuelle {
  entreprise_id: string;
  annee: number;
  mensualites: TvaMensuelle[];

  total_tva_collectee: string;
  total_tva_deductible_charges: string;
  total_tva_deductible_immobilisations: string;
  total_tva_deductible: string;
  total_tva_nette: string;

  total_tva_a_payer_technique: string;
  total_credit_tva_technique: string;
  nombre_mois_a_verifier: number;

  source_calcul: string;
  declaration_fiscale_prete: boolean;
  limites: string[];
}

export interface TvaConfiguration {
  id: string;
  cabinet_id: string;
  entreprise_id: string;
  periodicite: "mensuelle" | "trimestrielle" | "autre" | null;
  prorata_applicable: boolean | null;
  prorata_deduction: string | number | null;
  retenue_applicable: boolean | null;
  jour_limite_declaration: number | null;
  delai_saisie_topaze_jours: number | null;
  compte_tva_collectee: string | null;
  compte_tva_recuperable_charges: string | null;
  compte_tva_recuperable_immobilisations: string | null;
  compte_tva_a_payer: string | null;
  compte_credit_tva: string | null;
  notes: string | null;
}

export interface TvaPeriodeV2 {
  id: string;
  entreprise_id: string;
  annee: number;
  mois: number;
  statut: "provisoire" | "validee" | "cloturee" | string;
  tva_collectee: string | number;
  tva_recuperable_charges: string | number;
  tva_recuperable_immobilisations: string | number;
  credit_anterieur: string | number;
  regularisations: string | number;
  retenues_tva: string | number;
  tva_nette: string | number;
  tva_a_payer: string | number;
  credit_a_reporter: string | number;
  a_verifier: boolean;
  anomalies: string[];
  statut_comptable: "calcul_en_cours" | "a_verifier" | "prete_topaze" | "saisie_topaze" | string;
  statut_declaration: "a_preparer" | "a_verifier" | "prete_a_declarer" | "declaree" | "en_retard" | string;
  date_limite_declaration: string | null;
  declared_at: string | null;
  declared_by: string | null;
  declaration_date_reelle: string | null;
  declaration_reference: string | null;
  declaration_note: string | null;
  justificatif_disponible: boolean;
  topaze_entered_at: string | null;
  topaze_entered_by: string | null;
  topaze_batch_reference: string | null;
}

export interface TvaPeriodesAnnee {
  entreprise_id: string;
  annee: number;
  periodes: TvaPeriodeV2[];
  configuration: TvaConfiguration | null;
}
