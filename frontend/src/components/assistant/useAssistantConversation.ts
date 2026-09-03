import { useContext } from "react";

import { AssistantConversationContext } from "./assistantConversationStore";

export function useAssistantConversation() {
  const context = useContext(AssistantConversationContext);
  if (!context) throw new Error("AssistantConversationProvider manquant");
  return context;
}
