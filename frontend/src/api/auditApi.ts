import { apiClient } from "./client";
import type { AuditEvent, AuditFilters, AuditOptions, AuditPage } from "../types/audit";

export async function listAuditEvents(filters: AuditFilters): Promise<AuditPage> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== "" && value !== undefined),
  );
  const response = await apiClient.get<AuditPage>("/audit", { params });
  return response.data;
}

export async function getAuditEvent(id: string): Promise<AuditEvent> {
  const response = await apiClient.get<AuditEvent>(`/audit/${id}`);
  return response.data;
}

export async function getAuditOptions(): Promise<AuditOptions> {
  const response = await apiClient.get<AuditOptions>("/audit/options");
  return response.data;
}
