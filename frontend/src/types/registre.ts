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