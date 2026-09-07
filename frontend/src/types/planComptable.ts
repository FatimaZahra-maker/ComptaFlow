export type TypeUsageCompte =
  | "ht"
  | "tva"
  | "fournisseur"
  | "client"
  | "banque"
  | "gain_change"
  | "perte_change"
  | "autre";

export interface CompteComptableEntreprise {
  id: string;
  entreprise_id: string;
  numero_compte: string;
  libelle: string;
  famille_cgnc: string | null;
  type_usage: TypeUsageCompte;
  nature_comptable: string | null;
  tiers_nom: string | null;
  est_divers: boolean;
  is_active: boolean;
}

export interface CompteComptableCreate {
  numero_compte: string;
  libelle: string;
  famille_cgnc?: string | null;
  type_usage: TypeUsageCompte;
  nature_comptable?: string | null;
  tiers_nom?: string | null;
  est_divers?: boolean;
  is_active?: boolean;
}
