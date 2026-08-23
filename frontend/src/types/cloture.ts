export type TypeRegularisationCloture =
  | "amortissement"
  | "provision"
  | "stock"
  | "charge_constatee_avance"
  | "produit_constate_avance"
  | "charge_a_payer"
  | "produit_a_recevoir"
  | "ajustement_manuel"
  | "resultat_cloture"
  | "report_a_nouveau";

export interface RegularisationCloture {
  id: string;
  cabinet_id: string;
  entreprise_id: string;
  exercice: number;
  date_ecriture: string;
  type_regularisation: TypeRegularisationCloture;
  libelle: string;
  montant: string;
  compte_debit: string | null;
  compte_credit: string | null;
  statut: string;
  source: string;
  anomalies: string[];
  donnees_calcul: Record<string, unknown>;
  a_extourner: boolean;
  date_extourne: string | null;
}

export interface RegularisationClotureCreate {
  exercice: number;
  date_ecriture: string;
  type_regularisation: TypeRegularisationCloture;
  libelle: string;
  montant: number;
  compte_debit?: string;
  compte_credit?: string;
  donnees_calcul?: Record<string, unknown>;
}

