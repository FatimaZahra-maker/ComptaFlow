// Types correspondant au schéma Pydantic AlertesRappelsOut
// (backend/app/schemas/rappel.py).

export interface EcritureNonSaisie {
  id: string;
  entreprise_id: string;
  entreprise_nom: string;
  document_id: string;
  nom_fichier_document: string;
  tiers: string | null;
  numero_piece: string | null;
  date_piece: string | null;
  montant_ttc: string;
}

export interface EntrepriseEnRetard {
  entreprise_id: string;
  entreprise_nom: string;
  dernier_upload: string;
  delai_reference_jours: number;
  jours_depuis_dernier_upload: number;
  jours_de_retard: number;
}

export interface AlertesRappels {
  non_saisies: EcritureNonSaisie[];
  entreprises_en_retard: EntrepriseEnRetard[];
}