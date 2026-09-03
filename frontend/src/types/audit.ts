export interface AuditResourceLink {
  label: string;
  resource_type: string;
  resource_id: string;
  route: string;
}

export interface AuditEvent {
  id: string;
  cabinet_id: string;
  entreprise_id: string | null;
  entreprise_nom: string | null;
  user_id: string | null;
  actor_name: string | null;
  actor_email: string | null;
  actor_role: string | null;
  actor_type: string;
  action: string;
  module: string;
  resource_type: string | null;
  resource_id: string | null;
  description: string | null;
  status: "success" | "failed";
  event_at: string;
  correlation_id: string | null;
  item_count: number | null;
  resource_ids: string[];
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  links: AuditResourceLink[];
}

export interface AuditPage {
  items: AuditEvent[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface AuditOptions {
  actions: string[];
  modules: string[];
  roles: string[];
  statuses: string[];
}

export interface AuditFilters {
  page?: number;
  page_size?: number;
  search?: string;
  date_from?: string;
  date_to?: string;
  user_id?: string;
  role?: string;
  entreprise_id?: string;
  module?: string;
  action?: string;
  status?: string;
  sort?: "asc" | "desc";
}
