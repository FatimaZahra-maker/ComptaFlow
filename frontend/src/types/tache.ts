export type StatutTache = "a_faire" | "en_cours" | "terminee";
export type PrioriteTache = "basse" | "normale" | "haute";
export type RecurrenceTache = "aucune" | "mensuelle" | "trimestrielle" | "annuelle";

export interface Tache {
  id: string;
  entreprise_id: string | null;
  entreprise_nom: string | null;
  cree_par: string;
  assignee_a: string | null;
  assignee_nom: string | null;
  titre: string;
  description: string | null;
  date_echeance: string;
  heure_echeance: string | null;
  statut: StatutTache;
  priorite: PrioriteTache;
  recurrence: RecurrenceTache;
  created_at: string;
  est_en_retard: boolean;
}

export interface TacheCreatePayload {
  entreprise_id?: string;
  titre: string;
  description?: string;
  date_echeance: string;
  heure_echeance?: string;
  priorite?: PrioriteTache;
  recurrence?: RecurrenceTache;
}
export interface TacheUpdatePayload {
  titre?: string;
  description?: string | null;
  date_echeance?: string;
  heure_echeance?: string | null;
  statut?: StatutTache;
  priorite?: PrioriteTache;
  recurrence?: RecurrenceTache;
  assignee_a?: string | null;
}
