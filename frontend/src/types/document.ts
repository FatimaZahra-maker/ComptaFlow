export interface Document {
  id: string;
  nom_fichier_original: string;
  statut: "en_attente" | "en_traitement" | "traite" | "erreur";
  categorie: string | null;
  annee: number | null;
  mois: number | null;
  created_at: string;
}