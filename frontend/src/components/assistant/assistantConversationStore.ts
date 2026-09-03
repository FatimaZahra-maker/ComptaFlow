import { createContext } from "react";

import type { AssistantAction, AssistantResponse } from "../../types/assistant";
import type { Entreprise } from "../../types/entreprise";

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AssistantResponse;
}

export interface AssistantConversationValue {
  companies: Entreprise[];
  companyId: string;
  setCompanyId: (id: string) => void;
  messages: AssistantMessage[];
  input: string;
  setInput: (value: string) => void;
  loading: boolean;
  lastQuestion: string;
  submit: (question?: string) => Promise<void>;
  loadMore: () => Promise<void>;
  handleAction: (action: AssistantAction) => Promise<void>;
  openCompany: (entrepriseId: string, route: string | null) => void;
}

export const AssistantConversationContext = createContext<AssistantConversationValue | null>(null);
