export interface Rapport {
  entreprise_id: string;
  entreprise_nom: string;
  annee: number;
  mois: number | null;
  nombre_documents: number;
  nombre_documents_erreur: number;
  nombre_ecritures_validees: number;
  nombre_ecritures_a_verifier: number;
  nombre_anomalies: number;
  total_achats_ht: string;
  total_ventes_ht: string;
  tva_collectee: string;
  tva_deductible: string;
  tva_nette: string;
}