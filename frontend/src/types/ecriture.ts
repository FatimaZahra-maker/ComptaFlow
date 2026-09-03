export type StatutValidation =
  | "calcul_en_cours"
  | "brouillon"
  | "a_verifier"
  | "prete_topaze"
  | "saisie_topaze"
  | "valide"
  | "rejete";

export type TypeEcriture =
  | "achat"
  | "vente"
  | "banque"
  | "cnss"
  | "impot"
  | "autre";

export interface Ecriture {
  id: string;
  document_id: string;
  entreprise_id: string;
  type_ecriture: TypeEcriture | string;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  compte_tiers: string | null;
  compte_tva: string | null;
  compte_ht: string | null;
  libelle: string | null;
  montant_ht: string | null;
  taux_tva: string | null;
  montant_tva: string | null;
  montant_ttc: string;
  statut_validation: StatutValidation;
  anomalie_detectee: boolean;
  anomalie_details: string | null;
  doublon_potentiel_id: string | null;
  validated_by: string | null;
  created_at: string;
  saisie_topaze: boolean;
  ready_for_topaze_at: string | null;
  topaze_entered_at: string | null;
  topaze_entered_by: string | null;
  topaze_batch_reference: string | null;

  nom_fichier_document: string | null;
  entreprise_nom: string | null;
  categorie_document: string | null;
  statut_document: string | null;
}

export type PeriodiciteComptable = "mensuelle" | "trimestrielle" | "annuelle";

export interface EntryFilters {
  entreprise_id?: string;
  statut_validation?: StatutValidation;
  type_ecriture?: TypeEcriture;
  categorie?: string;
  recherche?: string;
  annee?: number;
  periodicite?: PeriodiciteComptable;
  mois?: number;
  trimestre?: number;
}

export interface EntryUpdatePayload {
  tiers?: string | null;
  numero_piece?: string | null;
  date_piece?: string | null;
  montant_ht?: string | null;
  taux_tva?: string | null;
  montant_tva?: string | null;
  montant_ttc?: string;
  compte_tiers?: string | null;
  compte_tva?: string | null;
  compte_ht?: string | null;
  libelle?: string | null;
}
