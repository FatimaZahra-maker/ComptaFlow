export interface Entreprise {
  id: string;
  nom: string;
  ice: string | null;
  creee_automatiquement: boolean;
  ecritures_brouillon?: number;
  ecritures_a_verifier?: number;
  ecritures_validees?: number;
}
