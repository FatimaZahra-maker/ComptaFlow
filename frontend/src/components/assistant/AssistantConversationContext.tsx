import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

import { askAssistant } from "../../api/assistantApi";
import { fetchApiBlob } from "../../api/client";
import { setActiveEntrepriseId } from "../../utils/activeEntreprise";
import { listEntreprises } from "../../api/entreprisesApi";
import { useAuth } from "../../context/AuthContext";
import type { AssistantAction } from "../../types/assistant";
import type { Entreprise } from "../../types/entreprise";
import {
  AssistantConversationContext,
  type AssistantMessage,
} from "./assistantConversationStore";

function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible.";
  }
  return "L'assistant ne peut pas répondre pour le moment.";
}

export function AssistantConversationProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const previousUserId = useRef<string | null>(null);
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [companyId, setCompanyIdState] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [contextDocumentId, setContextDocumentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastQuestion, setLastQuestion] = useState("");

  useEffect(() => {
    if (previousUserId.current === user?.id) return;
    previousUserId.current = user?.id ?? null;
    setMessages([]);
    setConversationId(null);
    setContextDocumentId(null);
    setCompanyIdState("");
    setInput("");
    setLastQuestion("");
    if (!user) {
      setCompanies([]);
      return;
    }
    listEntreprises()
      .then((items) => setCompanies(items.filter((item) => item.is_active !== false && !item.creee_automatiquement)))
      .catch(() => setCompanies([]));
  }, [user]);

  function setCompanyId(id: string) {
    setCompanyIdState(id);
    setContextDocumentId(null);
  }

  async function submitPage(question: string, page = 1, showQuestion = true) {
    const clean = question.trim();
    if (!clean || loading) return;
    setLastQuestion(clean);
    setInput("");
    setLoading(true);
    if (showQuestion) setMessages((current) => [...current, {
      id: crypto.randomUUID(), role: "user", text: clean,
    }]);
    try {
      const response = await askAssistant({
        question: clean,
        conversation_id: conversationId,
        context_document_id: contextDocumentId,
        entreprise_id: companyId || null,
        page,
      });
      setConversationId(response.conversation_id);
      if (response.context_document_id) setContextDocumentId(response.context_document_id);
      setMessages((current) => [...current, {
        id: crypto.randomUUID(), role: "assistant", text: response.message, response,
      }]);
    } catch (error) {
      setMessages((current) => [...current, {
        id: crypto.randomUUID(), role: "assistant", text: apiError(error),
      }]);
    } finally {
      setLoading(false);
    }
  }

  async function submit(question = input) {
    await submitPage(question, 1, true);
  }

  async function loadMore() {
    const lastResponse = [...messages].reverse().find((message) => message.response)?.response;
    if (!lastQuestion || !lastResponse?.has_more || loading) return;
    await submitPage(lastQuestion, lastResponse.page + 1, false);
  }

  async function handleAction(action: AssistantAction) {
    if (action.kind === "route" && action.route) {
      navigate(action.route);
      return;
    }
    if (action.kind === "secure_file" && action.api_path) {
      try {
        const blob = await fetchApiBlob(action.api_path);
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank", "noopener,noreferrer");
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } catch (error) {
        setMessages((current) => [...current, {
          id: crypto.randomUUID(), role: "assistant", text: apiError(error),
        }]);
      }
    }
  }

  function openCompany(entrepriseId: string, route: string | null) {
    setCompanyId(entrepriseId);
    setActiveEntrepriseId(entrepriseId);
    navigate(route ?? `/chronos?entreprise_id=${entrepriseId}`);
  }

  return <AssistantConversationContext.Provider value={{
    companies, companyId, setCompanyId, messages, input, setInput, loading,
    lastQuestion, submit, loadMore, handleAction, openCompany,
  }}>{children}</AssistantConversationContext.Provider>;
}
