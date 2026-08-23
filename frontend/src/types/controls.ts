export type ControlLevel = "bloquant" | "important" | "avertissement" | "information";

export interface ControlAnomaly {
  code: string;
  module: string;
  niveau: ControlLevel;
  titre: string;
  description: string;
  entreprise_id: string;
  exercice: number;
  objet_type: string;
  objet_id: string | null;
  route_frontend: string | null;
  metadata: Record<string, unknown>;
}

export interface ControlModuleSummary {
  module: string;
  statut: "ok" | "a_verifier" | "bloque";
  total_anomalies: number;
  bloquants: number;
  importants: number;
  avertissements: number;
  informations: number;
}

export interface PreClotureControls {
  entreprise_id: string;
  exercice: number;
  score: number;
  statut: "pret" | "a_verifier" | "bloque";
  resume: Record<string, ControlModuleSummary>;
  anomalies: ControlAnomaly[];
  avertissement_score: string;
  source_calcul: string;
}
