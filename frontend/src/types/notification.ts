export interface Notification {
  id: string;
  type: "document_erreur" | "ecriture_anomalie" | "ecriture_a_verifier" | "document_nouveau";
  message: string;
  route: string;
  created_at: string;
  entreprise_id: string | null;
  entreprise_nom: string | null;
}

export interface NotificationsResponse {
  total: number;
  notifications: Notification[];
}

export interface RepartitionParType {
  type: string;
  total: number;
}

export interface RepartitionParEntreprise {
  entreprise_id: string | null;
  entreprise_nom: string;
  total: number;
}

export interface NotificationsStats {
  par_type: RepartitionParType[];
  par_entreprise: RepartitionParEntreprise[];
}