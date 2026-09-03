import { useEffect, useRef, type KeyboardEvent } from "react";
import { useLocation } from "react-router-dom";
import {
  Bot, ExternalLink, FileSearch, Loader2, RefreshCw, Send, Sparkles, UserRound,
} from "lucide-react";

import type {
  AssistantAction, AssistantCompanyCard, AssistantDataCard, AssistantDocumentCard, AssistantResponse,
} from "../../types/assistant";
import { useAssistantConversation } from "./useAssistantConversation";

const SUGGESTIONS = [
  "Entreprises disponibles", "Factures à vérifier", "Factures non réglées",
  "Écritures non saisies dans Topaze", "Mouvements non rapprochés",
  "TVA de la période", "Tâches en retard", "Documents importés aujourd’hui",
];

function money(value: string | number | null, currency = "MAD") {
  if (value === null || value === undefined) return "Non disponible";
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? `${new Intl.NumberFormat("fr-MA", { minimumFractionDigits: 2 }).format(parsed)} ${currency}`
    : `${value} ${currency}`;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Non disponible";
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  if (Array.isArray(value)) return value.map((item) => typeof item === "object" ? "Élément détaillé" : String(item)).join(", ");
  if (typeof value === "object") return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${key.replaceAll("_", " ")} : ${String(item ?? "Non disponible")}`).join(" · ");
  return String(value);
}

function DocumentCard({ card, onAction }: {
  card: AssistantDocumentCard;
  onAction: (action: AssistantAction) => void;
}) {
  return <article className="mt-3 rounded-2xl border border-emerald-100 bg-white p-4 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="text-xs font-bold uppercase tracking-wide text-emerald-700">{card.categorie || "Document"}</p><h3 className="font-bold text-slate-900">{card.numero_facture || "Numéro non disponible"}</h3><p className="text-sm text-slate-500">{card.entreprise || "Entreprise à vérifier"} · {card.tiers || "Tiers non disponible"}</p></div>
      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">{card.statut_document}</span>
    </div>
    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4"><p><span className="text-slate-500">Date facture</span><br />{card.date_facture ? new Date(`${card.date_facture}T00:00:00`).toLocaleDateString("fr-MA") : "Non disponible"}</p><p><span className="text-slate-500">HT</span><br />{money(card.montant_ht, card.devise)}</p><p><span className="text-slate-500">TVA</span><br />{money(card.montant_tva, card.devise)}</p><p><span className="text-slate-500">TTC</span><br /><b>{money(card.montant_ttc, card.devise)}</b></p></div>
    {card.statut_paiement && <div className="mt-2 flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-blue-50 px-2 py-1 font-semibold text-blue-700">Paiement : {card.statut_paiement}</span><span className="rounded-full bg-slate-100 px-2 py-1">Réglé : {money(card.montant_regle)}</span><span className="rounded-full bg-amber-50 px-2 py-1 text-amber-800">Restant : {money(card.restant_du)}</span></div>}
    {card.donnees_extraites && <div className="mt-3 grid gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-2">{Object.entries(card.donnees_extraites).map(([key, value]) => <div key={key}><p className="text-[11px] font-bold uppercase text-slate-500">{key.replaceAll("_", " ")}</p><p className="break-words text-sm">{displayValue(value)}</p></div>)}</div>}
    {card.anomalies.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">{card.anomalies.join(" · ")}</div>}
    <div className="mt-4 flex flex-wrap gap-2">{card.actions.map((action) => <button type="button" key={`${action.kind}-${action.label}`} onClick={() => onAction(action)} className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-50"><ExternalLink size={14} />{action.label}</button>)}</div>
  </article>;
}

function CompanyCard({ card }: { card: AssistantCompanyCard }) {
  const { openCompany } = useAssistantConversation();
  const route = card.actions.find((action) => action.kind === "route")?.route ?? null;
  return <article data-testid="assistant-company-card" className="mt-3 rounded-2xl border border-emerald-100 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3"><div><h3 className="font-bold text-slate-900">{card.nom}</h3><p className="mt-1 break-all text-xs text-slate-500">Identifiant interne : {card.entreprise_id}</p>{card.ice && <p className="mt-1 text-sm text-slate-600">ICE : {card.ice}</p>}</div><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">{card.is_active ? "Active" : "Inactive"}</span></div>
    <button type="button" onClick={() => openCompany(card.entreprise_id, route)} className="mt-3 inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-800"><ExternalLink size={14} />Voir les documents</button>
  </article>;
}

function DataCard({ card, onAction }: { card: AssistantDataCard; onAction: (action: AssistantAction) => void }) {
  return <article className="mt-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-700">{card.resource_type.replaceAll("_", " ")}</p>
    <h3 className="font-bold text-slate-900">{card.title}</h3>
    {card.subtitle && <p className="text-sm text-slate-500">{card.subtitle}</p>}
    <div className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(card.fields).map(([key, value]) => <div key={key} className="rounded-lg bg-slate-50 p-2"><p className="text-[10px] font-bold uppercase text-slate-500">{key.replaceAll("_", " ")}</p><p className="break-words text-sm">{displayValue(value)}</p></div>)}</div>
    {card.actions.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{card.actions.map((action) => <button type="button" key={action.label} onClick={() => onAction(action)} className="inline-flex items-center gap-1 rounded-lg border border-emerald-200 px-3 py-2 text-xs font-bold text-emerald-800"><ExternalLink size={14} />{action.label}</button>)}</div>}
  </article>;
}

function ResultContent({ response }: { response: AssistantResponse }) {
  const { setInput, submit, loadMore, handleAction } = useAssistantConversation();
  const duplicate = response.clarification_question?.trim().toLocaleLowerCase("fr")
    === response.message.trim().toLocaleLowerCase("fr");
  return <div>
    {Object.keys(response.filters).length > 0 && <div className="mt-3 flex flex-wrap gap-1">{Object.entries(response.filters).map(([key, value]) => <span key={key} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">{key.replaceAll("_", " ")} : {displayValue(value)}</span>)}</div>}
    {response.companies.map((card) => <CompanyCard key={card.entreprise_id} card={card} />)}
    {response.documents.map((card) => <DocumentCard key={card.document_id} card={card} onAction={(action) => void handleAction(action)} />)}
    {response.payments.map((payment) => <div key={payment.mouvement_id} className="mt-3 rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm"><p className="font-bold">Règlement du {new Date(`${payment.date_operation}T00:00:00`).toLocaleDateString("fr-MA")}</p><p>{payment.libelle} · {money(payment.montant_affecte)} affectés · restant {money(payment.restant_du)}</p><div className="mt-2">{payment.actions.map((action) => <button type="button" key={action.label} onClick={() => void handleAction(action)} className="text-xs font-bold text-blue-700">{action.label} →</button>)}</div></div>)}
    {(response.data ?? []).map((card) => <DataCard key={`${card.resource_type}-${card.resource_id}`} card={card} onAction={(action) => void handleAction(action)} />)}
    {response.aggregate && <div className="mt-3 grid gap-2 rounded-xl bg-emerald-50 p-3 sm:grid-cols-2">{Object.entries(response.aggregate).map(([key, value]) => <div key={key}><p className="text-[11px] font-bold uppercase text-emerald-800">{key.replaceAll("_", " ")}</p><p className="break-words text-sm">{displayValue(value)}</p></div>)}</div>}
    {response.clarification_question && !duplicate && <button type="button" onClick={() => setInput(response.clarification_question ?? "")} className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-left text-sm font-semibold text-amber-800">{response.clarification_question}</button>}
    {response.warnings.map((warning) => <p key={warning} className="mt-2 text-xs text-amber-700">⚠ {warning}</p>)}
    <div className="mt-3 flex flex-wrap gap-2">{(response.suggestions ?? []).filter((item) => item !== "Voir plus de résultats").map((item) => <button type="button" key={item} onClick={() => void submit(item)} className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-xs text-emerald-800 hover:bg-emerald-50">{item}</button>)}{response.has_more && <button type="button" onClick={() => void loadMore()} className="rounded-full bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white">Voir plus de résultats</button>}</div>
  </div>;
}

export function AssistantConversation({ mode = "page" }: { mode?: "page" | "widget" }) {
  const endRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const { companies, companyId, setCompanyId, messages, input, setInput, loading, lastQuestion, submit } = useAssistantConversation();
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: "smooth" }); }, [messages, loading]);

  function handleKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(); }
  }

  const page = mode === "page";
  const initialSuggestions = companyId
    ? ["Factures non réglées", "Factures à vérifier", "TVA de la période", "Écritures non saisies dans Topaze", "Mouvements non rapprochés", "Tâches en retard"]
    : location.pathname.startsWith("/banque")
      ? ["Mouvements non rapprochés", "Afficher les paiements partiels", "Comptes bancaires disponibles", ...SUGGESTIONS.slice(0, 3)]
      : location.pathname.startsWith("/rappels")
        ? ["Tâches en retard", "Factures à vérifier", "Écritures non saisies dans Topaze", ...SUGGESTIONS.slice(0, 3)]
        : SUGGESTIONS;
  return <div data-testid={`assistant-conversation-${mode}`} className={`flex min-h-0 w-full flex-col ${page ? "mx-auto h-[calc(100vh-80px)] max-w-[1500px] p-4 sm:p-6" : "h-full"}`}>
    {page && <header className="mb-4 flex items-center gap-3"><div className="rounded-xl bg-emerald-700 p-2 text-white"><Bot /></div><div><h1 className="text-2xl font-bold text-slate-950">Assistant ComptaFlow</h1><p className="text-sm text-slate-500">Recherche sécurisée et lecture seule de vos données comptables.</p></div></header>}
    <div className={`flex items-center gap-2 border-slate-200 bg-white ${page ? "mb-3 rounded-xl border p-2" : "border-b px-3 py-2"}`}><label htmlFor={`assistant-company-${mode}`} className="shrink-0 text-xs font-semibold text-slate-500">Contexte</label><select id={`assistant-company-${mode}`} value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs"><option value="">Toutes les entreprises autorisées</option>{companies.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select></div>
    <main className={`min-h-0 flex-1 overflow-y-auto bg-slate-50 ${page ? "rounded-2xl border border-slate-200 p-3 sm:p-5" : "p-3"}`}>
      {messages.length === 0 && <div className={`mx-auto flex max-w-3xl flex-col items-center text-center ${page ? "py-12" : "py-6"}`}><Sparkles className="mb-3 text-emerald-700" size={page ? 38 : 30} /><h2 className="font-bold">Que souhaitez-vous rechercher ?</h2><p className="mt-2 max-w-xl text-sm text-slate-500">Je peux retrouver une entreprise, une facture, ses règlements, calculer la TVA ou lister les éléments à traiter.</p><div className="mt-4 flex flex-wrap justify-center gap-2">{initialSuggestions.map((item) => <button type="button" key={item} onClick={() => void submit(item)} className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-xs text-emerald-800 hover:bg-emerald-50">{item}</button>)}</div></div>}
      <div className="space-y-4">{messages.map((message) => <div key={message.id} className={`flex gap-2 ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${message.role === "user" ? "order-2 bg-slate-800 text-white" : "bg-emerald-700 text-white"}`}>{message.role === "user" ? <UserRound size={16} /> : <Bot size={16} />}</div><div className={`min-w-0 rounded-2xl p-3 ${page ? "max-w-4xl" : "max-w-[calc(100%-2.5rem)]"} ${message.role === "user" ? "bg-slate-800 text-white" : "border border-slate-200 bg-white text-slate-800 shadow-sm"}`}><p className="whitespace-pre-wrap text-sm">{message.text}</p>{message.response && <ResultContent response={message.response} />}</div></div>)}{loading && <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="animate-spin" size={17} /> Recherche dans les données autorisées…</div>}<div ref={endRef} /></div>
    </main>
    <footer className={`${page ? "mt-4" : "border-t border-slate-200 bg-white p-3"}`}><div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg"><FileSearch className="mb-2 text-slate-400" size={18} /><textarea aria-label="Question pour l'Assistant" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleKey} rows={mode === "widget" ? 1 : 2} placeholder="Ex. Quelles entreprises existent ?" className="max-h-28 min-h-10 flex-1 resize-none border-0 p-2 text-sm outline-none" /><button type="button" disabled={!input.trim() || loading} onClick={() => void submit()} className="rounded-xl bg-emerald-700 p-3 text-white disabled:opacity-40" aria-label="Envoyer"><Send size={18} /></button></div><div className="mt-1 flex items-center justify-between text-[10px] text-slate-500"><span>Entrée pour envoyer</span>{lastQuestion && <button type="button" disabled={loading} onClick={() => void submit(lastQuestion)} className="inline-flex items-center gap-1 font-semibold"><RefreshCw size={11} /> Réessayer</button>}</div></footer>
  </div>;
}
