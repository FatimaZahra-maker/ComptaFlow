// Types correspondant au schéma Pydantic DashboardOut
// (backend/app/schemas/dashboard.py).

export interface DocumentsParStatut {
  en_attente: number;
  en_traitement: number;
  traite: number;
  valide: number;
  erreur: number;
}

export interface EcrituresParStatutValidation {
  calcul_en_cours: number;
  brouillon: number;
  a_verifier: number;
  prete_topaze: number;
  saisie_topaze: number;
  valide: number;
  rejete: number;
}

export interface Dashboard {
  total_documents: number;
  documents_par_statut: DocumentsParStatut;

  total_ecritures: number;
  ecritures_par_statut: EcrituresParStatutValidation;

  tva_collectee: string;
  tva_deductible: string;
  tva_nette: string;

  total_entreprises: number;
}
