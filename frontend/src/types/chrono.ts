export interface DocumentChrono {
  id: string;
  nom_fichier_original: string;
  statut: string;
  categorie: string | null;
  annee: number | null;
  mois: number | null;
  entreprise_id: string | null;
  entreprise_nom: string | null;
  created_at: string;

  ecriture_id: string | null;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  montant_ht: string | null;
  taux_tva: string | null;
  montant_tva: string | null;
  montant_ttc: string | null;
  statut_validation: string | null;
  anomalie_detectee: boolean;
  anomalie_details: string | null;
  saisie_topaze: boolean;
}