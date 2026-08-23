export type StatutDocument =
  | "en_attente"
  | "en_traitement"
  | "traite"
  | "valide"
  | "erreur";

export interface Document {
  id: string;
  nom_fichier_original: string;
  statut: StatutDocument;
  categorie: string | null;
  annee: number | null;
  mois: number | null;
  date_piece: string | null;
  created_at: string;
  implique_cabinet: boolean;
  traitement_cabinet_propre: boolean;
  role_cabinet: string | null;
  taille_octets?: number | null;
  mime_type?: string | null;
  est_doublon: boolean;
  doublon_de_document_id: string | null;
}