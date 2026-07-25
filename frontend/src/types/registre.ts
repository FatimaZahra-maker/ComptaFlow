// Types correspondant au schéma Pydantic RegistreOut
// (backend/app/schemas/registre.py).
import type { Ecriture } from "./ecriture";

export interface Registre {
  categorie: string;
  entreprise_id: string;
  annee: number;
  mois: number;

  nombre: number;
  total_ht: string;
  total_tva: string;
  total_ttc: string;

  lignes: Ecriture[];
}
// --- Ajout : TVA ventilée par mois ---
export interface TvaMensuelle {
  mois: number;
  annee: number;
  tva_collectee: string;
  tva_deductible: string;
  tva_nette: string;
  nombre_ecritures: number;
}

export interface TvaAnnuelle {
  entreprise_id: string;
  annee: number;
  mensualites: TvaMensuelle[];
  total_tva_collectee: string;
  total_tva_deductible: string;
  total_tva_nette: string;
}