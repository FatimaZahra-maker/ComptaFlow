import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { ChevronLeft, ChevronRight, ExternalLink, History, RotateCcw, Search, X } from "lucide-react";

import { getAuditEvent, getAuditOptions, listAuditEvents } from "../api/auditApi";
import { listEntreprises } from "../api/entreprisesApi";
import { listUsers } from "../api/usersApi";
import type { AuditEvent, AuditOptions } from "../types/audit";
import type { Entreprise } from "../types/entreprise";
import type { UserAdmin } from "../types/user";

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super-administrateur", admin_cabinet: "Administrateur du cabinet",
  expert_comptable: "Expert-comptable", chef_mission: "Chef de mission",
  collaborateur: "Collaborateur", assistant: "Assistant",
};

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return typeof error.response?.data?.detail === "string"
      ? error.response.data.detail : "Le journal d'audit est indisponible.";
  }
  return "Une erreur inattendue est survenue.";
}

function readable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Non disponible";
  if (typeof value === "boolean") return value ? "Oui" : "Non";
  if (Array.isArray(value)) return value.map(readable).join(", ");
  if (typeof value === "object") return `${Object.keys(value as object).length} élément(s)`;
  return String(value);
}

function label(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Changes({ event }: { event: AuditEvent }) {
  const keys = Array.from(new Set([
    ...Object.keys(event.old_values ?? {}), ...Object.keys(event.new_values ?? {}),
  ])).filter((key) => event.old_values?.[key] !== event.new_values?.[key]);
  if (keys.length === 0) return <p className="text-sm text-slate-500">Aucune modification de champ enregistrée.</p>;
  return (
    <div className="space-y-2">
      {keys.map((key) => (
        <div key={key} className="grid gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-[150px_1fr_24px_1fr]">
          <span className="text-xs font-bold text-slate-600">{label(key)}</span>
          <span className="break-words rounded-lg bg-red-50 px-2 py-1 text-sm text-red-700">{readable(event.old_values?.[key])}</span>
          <span className="text-center text-slate-400">→</span>
          <span className="break-words rounded-lg bg-emerald-50 px-2 py-1 text-sm text-emerald-700">{readable(event.new_values?.[key])}</span>
        </div>
      ))}
    </div>
  );
}

export function AuditHistoryPage() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [options, setOptions] = useState<AuditOptions>({ actions: [], modules: [], roles: [], statuses: [] });
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [users, setUsers] = useState<UserAdmin[]>([]);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [module, setModule] = useState("");
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    Promise.all([getAuditOptions(), listEntreprises(), listUsers()])
      .then(([auditOptions, companyItems, userItems]) => {
        setOptions(auditOptions); setCompanies(companyItems); setUsers(userItems);
      })
      .catch((requestError) => setError(errorMessage(requestError)));
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const result = await listAuditEvents({
        page, page_size: 25, search: search.trim() || undefined,
        user_id: userId || undefined, role: role || undefined,
        entreprise_id: companyId || undefined, module: module || undefined,
        action: action || undefined, status: status || undefined, sort,
        date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
      });
      setEvents(result.items); setPages(result.pages); setTotal(result.total);
    } catch (requestError) {
      setError(errorMessage(requestError)); setEvents([]);
    } finally { setLoading(false); }
  }, [page, search, userId, role, companyId, module, action, status, dateFrom, dateTo, sort]);

  useEffect(() => { void load(); }, [load]);

  function reset() {
    setSearch(""); setUserId(""); setRole(""); setCompanyId(""); setModule("");
    setAction(""); setStatus(""); setDateFrom(""); setDateTo(""); setSort("desc"); setPage(1);
  }

  async function openDetail(event: AuditEvent) {
    setSelected(event); setDetailLoading(true);
    try { setSelected(await getAuditEvent(event.id)); }
    catch (requestError) { setError(errorMessage(requestError)); }
    finally { setDetailLoading(false); }
  }

  return (
    <div className="mx-auto w-full max-w-[1500px] p-4 sm:p-6 lg:p-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3"><History className="text-emerald-700" /><h1 className="text-2xl font-bold text-slate-950">Historique</h1></div>
          <p className="mt-1 text-sm text-slate-500">Journal immuable des actions réalisées dans votre cabinet.</p>
        </div>
        <p className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{total} événement(s)</p>
      </div>

      <section className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="relative mb-3"><Search className="absolute left-3 top-3 text-slate-400" size={17} /><input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Email, nom, numéro de facture, identifiant ou description…" className="w-full rounded-xl border border-slate-200 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-emerald-600" /></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          <select value={userId} onChange={(e) => { setUserId(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Tous les utilisateurs</option>{users.map((item) => <option key={item.id} value={item.id}>{item.prenom} {item.nom}</option>)}</select>
          <select value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Tous les rôles</option>{options.roles.map((item) => <option key={item} value={item}>{ROLE_LABELS[item] ?? label(item)}</option>)}</select>
          <select value={companyId} onChange={(e) => { setCompanyId(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Toutes les entreprises</option>{companies.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select>
          <select value={module} onChange={(e) => { setModule(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Tous les modules</option>{options.modules.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>
          <select value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Toutes les actions</option>{options.actions.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs"><option value="">Tous les statuts</option><option value="success">Réussie</option><option value="failed">Échouée</option></select>
          <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs" aria-label="Date de début" />
          <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1); }} className="rounded-lg border border-slate-200 p-2 text-xs" aria-label="Date de fin" />
        </div>
        <div className="mt-3 flex justify-end gap-2"><button onClick={() => setSort(sort === "desc" ? "asc" : "desc")} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Date {sort === "desc" ? "↓" : "↑"}</button><button onClick={reset} className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-2 text-xs font-semibold"><RotateCcw size={14} /> Réinitialiser</button></div>
      </section>

      {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? <div className="p-12 text-center text-sm text-slate-500">Chargement de l'historique…</div> : events.length === 0 ? <div className="p-12 text-center text-sm text-slate-500">Aucun événement ne correspond aux filtres.</div> : (
          <div className="divide-y divide-slate-100">{events.map((event) => (
            <button key={event.id} onClick={() => void openDetail(event)} className="grid w-full gap-3 p-4 text-left hover:bg-slate-50 md:grid-cols-[180px_1fr_180px_140px] md:items-center">
              <div><p className="text-sm font-bold text-slate-900">{event.actor_name || event.actor_email || "Système"}</p><p className="text-xs text-slate-500">{ROLE_LABELS[event.actor_role ?? ""] ?? label(event.actor_type)}</p></div>
              <div><p className="text-sm font-semibold text-slate-800">{event.description || label(event.action)}</p><p className="text-xs text-slate-500">{event.entreprise_nom || "Cabinet"} · {label(event.module)}{event.item_count ? ` · ${event.item_count} élément(s)` : ""}</p></div>
              <p className="text-xs text-slate-500">{new Intl.DateTimeFormat("fr-MA", { dateStyle: "short", timeStyle: "short" }).format(new Date(event.event_at))}</p>
              <span className={`w-fit rounded-full px-2 py-1 text-xs font-bold ${event.status === "success" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{event.status === "success" ? "Réussie" : "Échouée"}</span>
            </button>
          ))}</div>
        )}
      </section>
      <div className="mt-4 flex items-center justify-center gap-3"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronLeft size={18} /></button><span className="text-sm text-slate-600">Page {page} sur {pages}</span><button disabled={page >= pages} onClick={() => setPage((value) => value + 1)} className="rounded-lg border p-2 disabled:opacity-30"><ChevronRight size={18} /></button></div>

      {selected && <div className="fixed inset-0 z-[100] flex justify-end bg-slate-950/40" onClick={() => setSelected(null)}><aside onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-2xl"><div className="mb-5 flex items-start justify-between"><div><h2 className="text-xl font-bold">Détail de l'événement</h2><p className="text-xs text-slate-500">{selected.id}</p></div><button onClick={() => setSelected(null)} className="rounded-lg p-2 hover:bg-slate-100"><X /></button></div>{detailLoading ? <p className="text-sm text-slate-500">Chargement…</p> : <div className="space-y-6"><div className="grid gap-3 rounded-xl bg-slate-50 p-4 sm:grid-cols-2"><p><b>Acteur :</b> {selected.actor_name || selected.actor_email || "Système"}</p><p><b>Rôle :</b> {ROLE_LABELS[selected.actor_role ?? ""] ?? "Technique"}</p><p><b>Action :</b> {label(selected.action)}</p><p><b>Entreprise :</b> {selected.entreprise_nom || "Cabinet"}</p><p><b>Date :</b> {new Date(selected.event_at).toLocaleString("fr-MA")}</p><p><b>Statut :</b> {selected.status === "success" ? "Réussie" : "Échouée"}</p></div><section><h3 className="mb-2 font-bold">Champs modifiés</h3><Changes event={selected} /></section>{selected.metadata && <section><h3 className="mb-2 font-bold">Informations complémentaires</h3><div className="grid gap-2 sm:grid-cols-2">{Object.entries(selected.metadata).map(([key, value]) => <div key={key} className="rounded-lg border p-3"><p className="text-xs font-bold text-slate-500">{label(key)}</p><p className="break-words text-sm">{readable(value)}</p></div>)}</div></section>}{selected.resource_ids.length > 0 && <section><h3 className="mb-2 font-bold">Ressources groupées</h3><div className="flex flex-wrap gap-2">{selected.resource_ids.map((id) => <span key={id} className="rounded bg-slate-100 px-2 py-1 font-mono text-xs">{id}</span>)}</div></section>}{selected.links.map((item) => <button key={item.route} onClick={() => navigate(item.route)} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white"><ExternalLink size={16} /> {item.label}</button>)}</div>}</aside></div>}
    </div>
  );
}
