import { apiClient } from "./client";
import type { AssistantQuery, AssistantResponse } from "../types/assistant";

export async function askAssistant(payload: AssistantQuery): Promise<AssistantResponse> {
  const response = await apiClient.post<AssistantResponse>("/assistant/query", payload);
  return response.data;
}
