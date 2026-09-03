import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import axios from "axios";
import { CalendarClock, CheckCheck, Clock3, MessageCircle, RefreshCw, Send, UserRound, X } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getConversation, listMessageContacts, planMessageAsTask, sendCabinetMessage } from "../api/messagesApi";
import { useAuth } from "../context/AuthContext";
import type { CabinetMessage, MessageContact, MessageTaskPayload } from "../types/message";
import type { PrioriteTache, RecurrenceTache } from "../types/tache";

const ADMIN_ROLES = new Set(["admin_cabinet", "super_admin"]);
const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super-administrateur", admin_cabinet: "Administrateur",
  expert_comptable: "Expert-comptable", chef_mission: "Chef de mission",
  collaborateur: "Collaborateur", assistant: "Assistant",
};

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Le backend est inaccessible.";
  }
  return "Une erreur est survenue dans la messagerie.";
}

function messageTime(value: string): string {
  return new Date(value).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const DEFAULT_TASK: MessageTaskPayload = {
  titre: "",
  date_echeance: new Date().toISOString().slice(0, 10),
  heure_echeance: "09:00",
  priorite: "normale",
  recurrence: "aucune",
};

export function MessagesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = Boolean(user && ADMIN_ROLES.has(user.role));
  const [contacts, setContacts] = useState<MessageContact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CabinetMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [messageToPlan, setMessageToPlan] = useState<CabinetMessage | null>(null);
  const [taskForm, setTaskForm] = useState<MessageTaskPayload>(DEFAULT_TASK);
  const [planning, setPlanning] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(() => contacts.find((contact) => contact.id === selectedId) ?? null, [contacts, selectedId]);

  const refreshContacts = useCallback(async () => {
    try {
      const data = await listMessageContacts();
      setContacts(data);
      setSelectedId((current) => current && data.some((item) => item.id === current)
        ? current
        : data.find((item) => item.unread_count > 0)?.id ?? data[0]?.id ?? null);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }, []);

  const refreshConversation = useCallback(async (contactId: string, quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      setMessages(await getConversation(contactId));
      setContacts((current) => current.map((contact) => contact.id === contactId ? { ...contact, unread_count: 0 } : contact));
    } catch (caught) {
      if (!quiet) setError(errorMessage(caught));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshContacts();
    const timer = window.setInterval(() => void refreshContacts(), 10_000);
    return () => window.clearInterval(timer);
  }, [refreshContacts]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      setLoading(false);
      return;
    }
    void refreshConversation(selectedId);
    const timer = window.setInterval(() => void refreshConversation(selectedId, true), 5_000);
    return () => window.clearInterval(timer);
  }, [refreshConversation, selectedId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!selectedId || !content || sending) return;
    setSending(true);
    setError(null);
    try {
      const sent = await sendCabinetMessage(selectedId, content);
      setMessages((current) => [...current, sent]);
      setDraft("");
      await refreshContacts();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSending(false);
    }
  }

  function handleComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  function openPlanner(message: CabinetMessage) {
    setMessageToPlan(message);
    setTaskForm({ ...DEFAULT_TASK, titre: message.contenu.replace(/\s+/g, " ").slice(0, 120) });
  }

  async function planTask(event: FormEvent) {
    event.preventDefault();
    if (!messageToPlan || planning) return;
    setPlanning(true);
    setError(null);
    try {
      const task = await planMessageAsTask(messageToPlan.id, {
        ...taskForm,
        titre: taskForm.titre?.trim() || undefined,
        heure_echeance: taskForm.heure_echeance || undefined,
      });
      setMessages((current) => current.map((message) => message.id === messageToPlan.id ? { ...message, task_id: task.id } : message));
      setSuccess(`Tâche planifiée le ${new Date(`${task.date_echeance}T${task.heure_echeance ?? "00:00"}`).toLocaleString("fr-FR")}.`);
      setMessageToPlan(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setPlanning(false);
    }
  }

  return <div className="min-h-full bg-slate-50 p-4 lg:p-7">
    <div className="mx-auto max-w-[1500px]">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><MessageCircle className="text-green-600" /> Messagerie du cabinet</h1><p className="mt-1 text-sm text-slate-500">Échangez avec l’administrateur et transformez les instructions en tâches datées et horodatées.</p></div>
        <button type="button" onClick={() => { void refreshContacts(); if (selectedId) void refreshConversation(selectedId); }} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold"><RefreshCw size={16} /> Actualiser</button>
      </div>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 flex items-center justify-between rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700"><span>{success}</span><button type="button" onClick={() => navigate("/rappels")} className="font-semibold underline">Voir les tâches</button></div>}

      <div className="grid min-h-[680px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[330px_1fr]">
        <aside className="border-b border-slate-200 bg-slate-50/70 lg:border-b-0 lg:border-r">
          <div className="border-b px-4 py-4"><h2 className="font-bold text-slate-800">{isAdmin ? "Équipe du cabinet" : "Administrateurs"}</h2><p className="text-xs text-slate-500">{contacts.length} contact(s)</p></div>
          <div className="max-h-72 overflow-y-auto lg:max-h-[620px]">
            {contacts.length === 0 && <p className="p-5 text-sm text-slate-500">Aucun contact disponible.</p>}
            {contacts.map((contact) => <button key={contact.id} type="button" onClick={() => { setSelectedId(contact.id); setError(null); }} className={`flex w-full items-center gap-3 border-b px-4 py-4 text-left transition ${selectedId === contact.id ? "bg-green-50" : "hover:bg-white"}`}>
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${ADMIN_ROLES.has(contact.role) ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}><UserRound size={19} /></span>
              <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold text-slate-800">{contact.nom_complet}</span><span className="block truncate text-xs text-slate-500">{ROLE_LABELS[contact.role] ?? contact.role}{!contact.is_active ? " • désactivé" : ""}</span></span>
              {contact.unread_count > 0 && <span className="rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white">{contact.unread_count}</span>}
            </button>)}
          </div>
        </aside>

        <section className="flex min-h-[620px] min-w-0 flex-col">
          {!selected && <div className="grid flex-1 place-items-center p-8 text-center text-slate-400"><div><MessageCircle className="mx-auto mb-3" size={42} /><p>Sélectionnez un contact pour commencer une conversation.</p></div></div>}
          {selected && <>
            <header className="flex items-center gap-3 border-b px-5 py-4"><span className="grid h-10 w-10 place-items-center rounded-full bg-green-100 text-green-700"><UserRound size={19} /></span><div><h2 className="font-bold text-slate-900">{selected.nom_complet}</h2><p className="text-xs text-slate-500">{ROLE_LABELS[selected.role] ?? selected.role} • {selected.email}</p></div></header>
            <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50/50 p-4 sm:p-6">
              {loading && <p className="text-center text-sm text-slate-400">Chargement de la conversation...</p>}
              {!loading && messages.length === 0 && <p className="py-10 text-center text-sm text-slate-400">Aucun message. Vous pouvez démarrer la conversation.</p>}
              {messages.map((message) => <article key={message.id} className={`group flex ${message.is_mine ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[82%] rounded-2xl px-4 py-3 shadow-sm ${message.is_mine ? "rounded-br-md bg-green-600 text-white" : message.message_type === "access_request" ? "rounded-bl-md border border-orange-200 bg-orange-50 text-slate-800" : "rounded-bl-md border bg-white text-slate-800"}`}>
                  {message.message_type === "access_request" && <span className="mb-2 inline-flex rounded-full bg-orange-100 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-orange-700">Renouvellement d’accès</span>}
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{message.contenu}</p>
                  <div className={`mt-2 flex flex-wrap items-center justify-end gap-2 text-[10px] ${message.is_mine ? "text-green-100" : "text-slate-400"}`}><span>{messageTime(message.created_at)}</span>{message.is_mine && message.read_at && <CheckCheck size={13} />}{message.task_id && <button type="button" onClick={() => navigate("/rappels")} className="inline-flex items-center gap-1 font-semibold underline"><CalendarClock size={12} /> Tâche créée</button>}</div>
                  {isAdmin && !message.task_id && <button type="button" onClick={() => openPlanner(message)} className={`mt-2 inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold ${message.is_mine ? "bg-white/15 text-white hover:bg-white/25" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}><Clock3 size={13} /> Planifier comme tâche</button>}
                </div>
              </article>)}
              <div ref={bottomRef} />
            </div>
            <form onSubmit={(event) => void send(event)} className="border-t bg-white p-4"><div className="flex items-end gap-3"><textarea aria-label="Votre message" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKey} rows={2} maxLength={2000} placeholder={selected.is_active ? "Écrivez votre message… (Entrée pour envoyer)" : "Ce compte est désactivé"} disabled={!selected.is_active || sending} className="min-h-12 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-green-500 focus:ring-4 focus:ring-green-500/10" /><button type="submit" disabled={!draft.trim() || !selected.is_active || sending} className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-green-600 text-white hover:bg-green-700 disabled:opacity-40" aria-label="Envoyer le message"><Send size={19} /></button></div></form>
          </>}
        </section>
      </div>
    </div>

    {messageToPlan && <div className="fixed inset-0 z-[10000] grid place-items-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-labelledby="planner-title"><form onSubmit={(event) => void planTask(event)} className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl"><div className="mb-5 flex items-start justify-between"><div><h2 id="planner-title" className="text-lg font-bold">Planifier ce message</h2><p className="text-sm text-slate-500">La tâche apparaîtra dans Rappels & Tâches à la date et l’heure précisées.</p></div><button type="button" onClick={() => setMessageToPlan(null)} className="rounded-lg p-2 hover:bg-slate-100" aria-label="Fermer"><X size={18} /></button></div><blockquote className="mb-4 max-h-28 overflow-y-auto rounded-xl border-l-4 border-green-500 bg-slate-50 p-3 text-sm text-slate-600">{messageToPlan.contenu}</blockquote><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm sm:col-span-2">Titre<input required maxLength={255} value={taskForm.titre} onChange={(event) => setTaskForm({ ...taskForm, titre: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label><label className="text-sm">Date<input required type="date" value={taskForm.date_echeance} onChange={(event) => setTaskForm({ ...taskForm, date_echeance: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label><label className="text-sm">Heure<input type="time" value={taskForm.heure_echeance ?? ""} onChange={(event) => setTaskForm({ ...taskForm, heure_echeance: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label><label className="text-sm">Priorité<select value={taskForm.priorite} onChange={(event) => setTaskForm({ ...taskForm, priorite: event.target.value as PrioriteTache })} className="mt-1 w-full rounded-lg border px-3 py-2.5"><option value="basse">Basse</option><option value="normale">Normale</option><option value="haute">Haute</option></select></label><label className="text-sm">Récurrence<select value={taskForm.recurrence} onChange={(event) => setTaskForm({ ...taskForm, recurrence: event.target.value as RecurrenceTache })} className="mt-1 w-full rounded-lg border px-3 py-2.5"><option value="aucune">Ponctuelle</option><option value="mensuelle">Mensuelle</option><option value="trimestrielle">Trimestrielle</option><option value="annuelle">Annuelle</option></select></label></div><div className="mt-6 flex justify-end gap-2"><button type="button" onClick={() => setMessageToPlan(null)} className="rounded-lg border px-4 py-2 text-sm font-semibold">Annuler</button><button type="submit" disabled={planning} className="rounded-lg bg-green-600 px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">{planning ? "Planification..." : "Créer la tâche"}</button></div></form></div>}
  </div>;
}
