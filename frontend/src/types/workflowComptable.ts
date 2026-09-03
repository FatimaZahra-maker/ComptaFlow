export interface WorkPeriod {
  id: string;
  entreprise_id: string;
  exercice: number;
  periode_debut: string;
  periode_fin: string;
  date_limite_saisie_topaze: string | null;
  verrouillee: boolean;
  locked_at: string | null;
  locked_by: string | null;
  reopened_at: string | null;
  reopened_by: string | null;
  reopen_reason: string | null;
}

export interface ExpectedDocument {
  id: string;
  entreprise_id: string;
  type_document: string;
  frequence: string;
  periode_debut: string;
  periode_fin: string;
  date_limite_reception: string;
  nombre_attendu: number | null;
  responsable_id: string | null;
  complete_manuellement: boolean;
  documents_recus: number;
  documents_manquants: number | null;
  jours_retard: number;
  statut: string;
}
