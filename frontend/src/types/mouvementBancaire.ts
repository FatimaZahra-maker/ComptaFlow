export type TypeMouvementBancaire = "debit" | "credit";

export type StatutRapprochement =
  | "non_rapproche"
  | "propose"
  | "automatique"
  | "confirme"
  | "ambigu";

export type ModeRapprochement = "simple" | "partiel" | "groupe" | "special";

export type NatureOperationBancaire =
  | "reglement_facture"
  | "acompte"
  | "frais_bancaire"
  | "virement_interne"
  | "autre";

export interface AllocationRapprochement {
  id: string;
  ecriture_id: string;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  type_ecriture: string | null;
  montant_ttc: string | number | null;
  montant_affecte: string | number;
  montant_restant_facture_apres: string | number | null;
  statut: string;
  score: string | number | null;
  raison: string | null;
}

export interface AllocationRapprochementInput {
  ecriture_id: string;
  montant_affecte: string | number;
}

export interface MouvementBancaire {
  id: string;
  document_id: string;
  entreprise_id: string;
  date_operation: string;
  libelle: string;
  reference: string | null;
  type_mouvement: TypeMouvementBancaire | string;
  montant: string | number;
  solde_apres_operation: string | number | null;

  devise_originale: string;
  montant_devise: string | number | null;
  montant_mad: string | number | null;
  taux_change: string | number | null;
  type_cours_change: string | null;
  date_cours_change: string | null;
  unite_cotation: number | null;
  source_cours_change: string | null;

  compte_bancaire_entreprise_id: string | null;
  nature_operation: NatureOperationBancaire | string;
  compte_contrepartie: string | null;
  mouvement_lie_id: string | null;

  ecriture_rapprochee_id: string | null;
  statut_rapprochement: StatutRapprochement | string;
  mode_rapprochement: ModeRapprochement | string;
  score_rapprochement: string | number | null;
  raison_rapprochement: string | null;
  compte_banque: string | null;
  rapprochement_confirme_par: string | null;
  date_rapprochement: string | null;

  created_at?: string | null;
}

export interface MouvementBancaireUpdate {
  date_operation?: string;
  libelle?: string;
  reference?: string | null;
  type_mouvement?: TypeMouvementBancaire;
  montant?: string;
  solde_apres_operation?: string | null;
  compte_bancaire_entreprise_id?: string | null;
  nature_operation?: NatureOperationBancaire;
  compte_contrepartie?: string | null;
  mouvement_lie_id?: string | null;
}

export interface MouvementBancaireListe extends MouvementBancaire {
  entreprise_nom: string | null;
  nom_fichier_document: string;
  statut_document: string;
  annee: number | null;
  mois: number | null;
  saisie_topaze: boolean;

  numero_piece_rapprochee: string | null;
  date_piece_rapprochee: string | null;
  tiers_rapproche: string | null;
  type_ecriture_rapprochee: string | null;
  montant_ttc_rapproche: string | number | null;

  montant_affecte_total: string | number;
  montant_non_affecte: string | number;
  nombre_allocations: number;
  allocations: AllocationRapprochement[];

  compte_bancaire_libelle: string | null;
  compte_bancaire_rib: string | null;
  compte_bancaire_iban: string | null;
}

export interface RapprochementCandidat {
  ecriture_id: string;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  type_ecriture: string;
  montant_ttc: string | number;
  montant_deja_regle: string | number;
  montant_restant: string | number;
  montant_suggere: string | number;
  type_suggestion: "simple" | "partiel" | "groupe" | string;
  score: string | number;
  raisons: string[];
}

export interface VirementInterneCandidat {
  mouvement_id: string;
  date_operation: string;
  libelle: string;
  type_mouvement: string;
  montant: string | number;
  compte_banque: string | null;
  score: string | number;
  raisons: string[];
}

export interface CompteBancaireEntreprise {
  id: string;
  entreprise_id: string;
  libelle: string;
  banque_nom: string | null;
  rib: string | null;
  iban: string | null;
  bic_swift: string | null;
  devise: string;
  numero_compte_comptable: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CompteBancaireCreate {
  entreprise_id: string;
  libelle: string;
  banque_nom?: string | null;
  rib?: string | null;
  iban?: string | null;
  bic_swift?: string | null;
  devise?: string;
  numero_compte_comptable: string;
}

export interface BankMovementFilters {
  entreprise_id?: string;
  type_mouvement?: TypeMouvementBancaire;
  recherche?: string;
  annee?: number;
  mois?: number;
}
