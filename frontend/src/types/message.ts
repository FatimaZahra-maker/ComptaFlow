import type { PrioriteTache, RecurrenceTache, Tache } from "./tache";

export interface MessageContact {
  id: string;
  nom_complet: string;
  email: string;
  role: string;
  is_active: boolean;
  unread_count: number;
}

export interface CabinetMessage {
  id: string;
  sender_id: string | null;
  recipient_id: string | null;
  sender_name: string | null;
  recipient_name: string | null;
  contenu: string;
  message_type: "chat" | "access_request";
  read_at: string | null;
  task_id: string | null;
  created_at: string;
  is_mine: boolean;
}

export interface MessageTaskPayload {
  titre?: string;
  date_echeance: string;
  heure_echeance?: string;
  priorite: PrioriteTache;
  recurrence: RecurrenceTache;
}

export type PlannedMessageTask = Tache;
