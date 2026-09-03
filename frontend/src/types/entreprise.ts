export interface Entreprise {
  id: string;
  nom: string;
  ice: string | null;
  identifiant_fiscal: string | null;
  rc: string | null;
  is_active?: boolean;
  creee_automatiquement: boolean;
  ecritures_brouillon?: number;
  ecritures_a_verifier?: number;
  ecritures_validees?: number;
}
