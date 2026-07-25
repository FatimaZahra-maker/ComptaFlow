import type { MouvementBancaire } from "./mouvementBancaire";

export interface EcritureResume {
  id: string;
  type_ecriture: string;
  numero_piece: string | null;
  date_piece: string | null;
  tiers: string | null;
  montant_ht: string | null;
  taux_tva: string | null;
  montant_tva: string | null;
  montant_ttc: string;
  statut_validation: string;
  anomalie_detectee: boolean;
  anomalie_details: string | null;
}

export interface DocumentDetail {
  id: string;
  nom_fichier_original: string;
  taille_octets: number | null;
  mime_type: string | null;
  statut: "en_attente" | "en_traitement" | "traite" | "valide" | "erreur";
  created_at: string;

  entreprise_id: string | null;
  annee: number | null;
  mois: number | null;
  categorie: string | null;

  texte_ocr: string | null;
  donnees_extraites: Record<string, unknown> | null;
  message_erreur: string | null;

  ecriture: EcritureResume | null;
  mouvements_bancaires?: MouvementBancaire[] | null;
}