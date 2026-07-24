export interface Ecriture {
  id: string;
  document_id: string;
  entreprise_id: string;
  type_ecriture: string;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  montant_ht: string;
  taux_tva: string;
  montant_tva: string;
  montant_ttc: string;
  statut_validation: "brouillon" | "a_verifier" | "valide" | "rejete";
  anomalie_detectee: boolean;
  anomalie_details: string | null;
  doublon_potentiel_id: string | null;
  validated_by: string | null;
  created_at: string;
}