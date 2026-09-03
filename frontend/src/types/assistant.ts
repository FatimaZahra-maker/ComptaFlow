export interface AssistantAction {
  label: string;
  kind: "route" | "secure_file";
  route: string | null;
  api_path: string | null;
  filename: string | null;
}

export interface AssistantDocumentCard {
  document_id: string;
  entreprise_id: string | null;
  entreprise: string | null;
  categorie: string | null;
  tiers: string | null;
  numero_facture: string | null;
  date_facture: string | null;
  date_importation: string;
  montant_ht: string | number | null;
  montant_tva: string | number | null;
  montant_ttc: string | number | null;
  devise: string;
  statut_document: string;
  statut_ecriture: string | null;
  statut_paiement: string | null;
  montant_regle: string | number | null;
  restant_du: string | number | null;
  saisie_topaze: boolean;
  anomalies: string[];
  donnees_extraites: Record<string, unknown> | null;
  actions: AssistantAction[];
}

export interface AssistantPaymentCard {
  mouvement_id: string;
  ecriture_id: string;
  date_operation: string;
  montant_mouvement: string | number;
  montant_affecte: string | number;
  restant_du: string | number;
  reference: string | null;
  libelle: string;
  statut: string;
  actions: AssistantAction[];
}

export interface AssistantCompanyCard {
  entreprise_id: string;
  nom: string;
  ice: string | null;
  identifiant_fiscal: string | null;
  is_active: boolean;
  actions: AssistantAction[];
}

export interface AssistantDataCard {
  resource_type: string;
  resource_id: string;
  title: string;
  subtitle: string | null;
  fields: Record<string, unknown>;
  actions: AssistantAction[];
}

export interface AssistantResponse {
  conversation_id: string;
  response_type: "single_document" | "document_list" | "company_list" | "data_list" | "message" | "aggregate" | "accounting_detail" | "clarification" | "no_result" | "error";
  intent: string;
  message: string;
  filters: Record<string, unknown>;
  documents: AssistantDocumentCard[];
  companies: AssistantCompanyCard[];
  payments: AssistantPaymentCard[];
  data: AssistantDataCard[];
  total_count: number | null;
  aggregate: Record<string, unknown> | null;
  sources: Array<{ resource_type: string; resource_id: string; label: string; route: string | null }>;
  warnings: string[];
  clarification_question: string | null;
  context_document_id: string | null;
  suggestions: string[];
  plan_summary: Record<string, unknown>;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface AssistantQuery {
  question: string;
  conversation_id?: string | null;
  context_document_id?: string | null;
  entreprise_id?: string | null;
  page?: number;
}
