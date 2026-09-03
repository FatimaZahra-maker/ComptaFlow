import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  AlertTriangle,
  BellRing,
  CalendarClock,
  CheckCircle2,
  CircleDot,
  Columns3,
  Download,
  FileText,
  Plus,
  RefreshCw,
  Search,
  ListTodo,
  Trash2,
  X,
} from "lucide-react";

import { listEntreprises } from "../api/entreprisesApi";
import {
  createTache,
  deleteTache,
  listTaches,
  terminerTache,
  updateTache,
} from "../api/tachesApi";
import { getAlertesRappels } from "../api/rappelsApi";
import { toggleSaisieTopaze } from "../api/accountingApi";
import type { Entreprise } from "../types/entreprise";
import type {
  PrioriteTache,
  RecurrenceTache,
  StatutTache,
  Tache,
} from "../types/tache";
import type { AlertesRappels } from "../types/rappel";
import {
  exportRowsToCsv,
  exportRowsToExcel,
  type ExportColumn,
} from "../utils/tableExport";

const STATUS_LABELS: Record<StatutTache, string> = {
  a_faire: "À faire",
  en_cours: "En cours",
  terminee: "Terminée",
};

const STATUS_CLASSES: Record<StatutTache, string> = {
  a_faire: "bg-slate-100 text-slate-700",
  en_cours: "bg-blue-100 text-blue-700",
  terminee: "bg-green-100 text-green-700",
};

const PRIORITY_CLASSES: Record<PrioriteTache, string> = {
  basse: "bg-slate-100 text-slate-600",
  normale: "bg-amber-100 text-amber-700",
  haute: "bg-red-100 text-red-700",
};

const RECURRENCE_LABELS: Record<RecurrenceTache, string> = {
  aucune: "Ponctuelle",
  mensuelle: "Mensuelle",
  trimestrielle: "Trimestrielle",
  annuelle: "Annuelle",
};

const EMPTY_FORM = {
  entreprise_id: "",
  titre: "",
  description: "",
  date_echeance: new Date().toISOString().slice(0, 10),
  heure_echeance: "09:00",
  priorite: "normale" as PrioriteTache,
  recurrence: "aucune" as RecurrenceTache,
};

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Backend inaccessible. Vérifiez Uvicorn.";
    const detail = error.response.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return "Une erreur est survenue.";
}

function formatMoney(value: string): string {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed)
    ? `${new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(parsed)} MAD`
    : "—";
}

function dueLabel(task: Tache): string {
  const due = new Date(`${task.date_echeance}T${task.heure_echeance?.slice(0, 5) || "23:59"}:00`);
  const today = new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startDue = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const days = Math.round((startDue.getTime() - startToday.getTime()) / 86_400_000);
  const time = task.heure_echeance ? ` à ${task.heure_echeance.slice(0, 5)}` : "";
  if (days === 0) return `Aujourd'hui${time}`;
  if (days === 1) return `Demain${time}`;
  if (days === -1) return `Hier${time}`;
  return `${startDue.toLocaleDateString("fr-FR")}${time}`;
}

export function RappelsPage() {
  const navigate = useNavigate();

  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [alertes, setAlertes] = useState<AlertesRappels | null>(null);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [statut, setStatut] = useState<StatutTache | "">("");
  const [priorite, setPriorite] = useState<PrioriteTache | "">("");
  const [search, setSearch] = useState("");
  const [onlyLate, setOnlyLate] = useState(false);
  const [viewMode, setViewMode] = useState<"board" | "list">("board");
  const [loading, setLoading] = useState(true);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    listEntreprises().then(setEntreprises).catch(() => setEntreprises([]));
  }, []);

  const refreshTasks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTaches({
        entreprise_id: entrepriseId || undefined,
        statut: statut || undefined,
        seulement_en_retard: onlyLate || undefined,
      });
      setTaches(data);
    } catch (requestError) {
      setTaches([]);
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, onlyLate, statut]);

  const refreshAlerts = useCallback(async () => {
    setLoadingAlerts(true);
    try {
      setAlertes(await getAlertesRappels());
    } catch {
      setAlertes(null);
    } finally {
      setLoadingAlerts(false);
    }
  }, []);

  useEffect(() => {
    void refreshTasks();
  }, [refreshTasks]);

  useEffect(() => {
    void refreshAlerts();
  }, [refreshAlerts]);

  const visibleTasks = useMemo(() => {
    const term = search.trim().toLowerCase();
    return taches.filter((task) => {
      if (priorite && task.priorite !== priorite) return false;
      if (!term) return true;
      return [task.titre, task.description, task.entreprise_nom, task.assignee_nom]
        .some((value) => value?.toLowerCase().includes(term));
    });
  }, [priorite, search, taches]);

  const metrics = useMemo(() => ({
    total: taches.length,
    toDo: taches.filter((task) => task.statut === "a_faire").length,
    inProgress: taches.filter((task) => task.statut === "en_cours").length,
    late: taches.filter((task) => task.est_en_retard).length,
  }), [taches]);

  const exportColumns: ExportColumn<Tache>[] = [
    { header: "Titre", value: (task) => task.titre },
    { header: "Entreprise", value: (task) => task.entreprise_nom ?? "Cabinet" },
    { header: "Description", value: (task) => task.description ?? "" },
    { header: "Échéance", value: (task) => `${new Date(`${task.date_echeance}T00:00:00`).toLocaleDateString("fr-FR")}${task.heure_echeance ? ` à ${task.heure_echeance.slice(0, 5)}` : ""}` },
    { header: "Statut", value: (task) => STATUS_LABELS[task.statut] },
    { header: "Priorité", value: (task) => task.priorite },
    { header: "Récurrence", value: (task) => RECURRENCE_LABELS[task.recurrence] },
    { header: "En retard", value: (task) => task.est_en_retard ? "Oui" : "Non" },
  ];

  async function submitTask(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    try {
      await createTache({
        entreprise_id: form.entreprise_id || undefined,
        titre: form.titre.trim(),
        description: form.description.trim() || undefined,
        date_echeance: form.date_echeance,
        heure_echeance: form.heure_echeance || undefined,
        priorite: form.priorite,
        recurrence: form.recurrence,
      });
      setForm(EMPTY_FORM);
      setFormOpen(false);
      setSuccess("Tâche créée avec succès.");
      await refreshTasks();
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  async function changeStatus(task: Tache, nextStatus: StatutTache): Promise<void> {
    setBusyId(task.id);
    setError(null);
    try {
      if (nextStatus === "terminee") await terminerTache(task.id);
      else await updateTache(task.id, { statut: nextStatus });
      await refreshTasks();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusyId(null);
    }
  }

  async function removeTask(id: string): Promise<void> {
    if (!window.confirm("Supprimer définitivement cette tâche ?")) return;
    setBusyId(id);
    try {
      await deleteTache(id);
      await refreshTasks();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusyId(null);
    }
  }

  async function markEntryDone(id: string): Promise<void> {
    setBusyId(id);
    try {
      await toggleSaisieTopaze(id);
      await refreshAlerts();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusyId(null);
    }
  }

  function createReminder(enterpriseId: string, enterpriseName: string): void {
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + 3);
    setForm({
      ...EMPTY_FORM,
      entreprise_id: enterpriseId,
      titre: `Relancer ${enterpriseName} pour les pièces manquantes`,
      description: "Contacter l’entreprise et confirmer la date d’envoi des documents comptables.",
      date_echeance: dueDate.toISOString().slice(0, 10),
      priorite: "haute",
    });
    setFormOpen(true);
  }

  return (
    <div className="min-h-full bg-slate-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1650px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Rappels & Tâches</h1>
            <p className="mt-1 text-sm text-slate-500">Pilotage des échéances, relances clients et opérations comptables à terminer.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => exportRowsToCsv("taches_comptaflow.csv", visibleTasks, exportColumns)} disabled={visibleTasks.length === 0} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"><Download size={16} /> CSV</button>
            <button type="button" onClick={() => exportRowsToExcel("taches_comptaflow.xls", "Tâches", visibleTasks, exportColumns)} disabled={visibleTasks.length === 0} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"><Download size={16} /> Excel</button>
            <button type="button" onClick={() => { void refreshTasks(); void refreshAlerts(); }} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold"><RefreshCw size={16} /> Actualiser</button>
            <button type="button" onClick={() => setFormOpen((open) => !open)} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"><Plus size={16} /> Nouvelle tâche</button>
          </div>
        </div>

        {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Total tâches", metrics.total, CalendarClock, "text-slate-700 bg-slate-100"],
            ["À faire", metrics.toDo, CircleDot, "text-amber-700 bg-amber-100"],
            ["En cours", metrics.inProgress, RefreshCw, "text-blue-700 bg-blue-100"],
            ["En retard", metrics.late, AlertTriangle, "text-red-700 bg-red-100"],
          ].map(([label, value, Icon, style]) => {
            const MetricIcon = Icon as typeof CalendarClock;
            return <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><div><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{String(label)}</p><p className="mt-2 text-2xl font-bold">{String(value)}</p></div><div className={`rounded-xl p-3 ${String(style)}`}><MetricIcon size={22} /></div></div></div>;
          })}
        </section>

        {formOpen && (
          <form onSubmit={(event) => void submitTask(event)} className="mb-6 rounded-2xl border border-green-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between"><div><h2 className="font-bold">Créer une tâche opérationnelle</h2><p className="text-xs text-slate-500">Une tâche récurrente génère automatiquement sa prochaine échéance lorsqu’elle est terminée.</p></div><button type="button" onClick={() => setFormOpen(false)} className="rounded-lg p-2 hover:bg-slate-100"><X size={18} /></button></div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <label className="xl:col-span-2 text-sm">Titre<input required value={form.titre} onChange={(event) => setForm({ ...form, titre: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" placeholder="Ex. Préparer la déclaration TVA" /></label>
              <label className="text-sm">Entreprise<select value={form.entreprise_id} onChange={(event) => setForm({ ...form, entreprise_id: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5"><option value="">Cabinet — tâche générale</option>{entreprises.map((enterprise) => <option key={enterprise.id} value={enterprise.id}>{enterprise.nom}</option>)}</select></label>
              <label className="text-sm xl:col-span-3">Description<textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
              <label className="text-sm">Échéance<input type="date" required value={form.date_echeance} onChange={(event) => setForm({ ...form, date_echeance: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
              <label className="text-sm">Heure<input type="time" value={form.heure_echeance} onChange={(event) => setForm({ ...form, heure_echeance: event.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2.5" /></label>
              <label className="text-sm">Priorité<select value={form.priorite} onChange={(event) => setForm({ ...form, priorite: event.target.value as PrioriteTache })} className="mt-1 w-full rounded-lg border px-3 py-2.5"><option value="basse">Basse</option><option value="normale">Normale</option><option value="haute">Haute</option></select></label>
              <label className="text-sm">Récurrence<select value={form.recurrence} onChange={(event) => setForm({ ...form, recurrence: event.target.value as RecurrenceTache })} className="mt-1 w-full rounded-lg border px-3 py-2.5"><option value="aucune">Ponctuelle</option><option value="mensuelle">Mensuelle</option><option value="trimestrielle">Trimestrielle</option><option value="annuelle">Annuelle</option></select></label>
            </div>
            <div className="mt-5 flex justify-end"><button type="submit" className="rounded-lg bg-green-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-green-700">Créer la tâche</button></div>
          </form>
        )}

        <div className="mb-6 grid gap-5 xl:grid-cols-2">
          <section className="overflow-hidden rounded-xl border border-orange-200 bg-white shadow-sm">
            <div className="border-b bg-orange-50 px-5 py-4"><h2 className="flex items-center gap-2 font-bold text-orange-900"><BellRing size={18} /> Entreprises à relancer</h2><p className="text-xs text-orange-700">Retards estimés à partir du rythme habituel de réception des pièces.</p></div>
            {loadingAlerts && <p className="p-5 text-sm text-slate-400">Chargement...</p>}
            {!loadingAlerts && (!alertes || alertes.entreprises_en_retard.length === 0) && <p className="p-5 text-sm text-slate-400">Aucune relance automatique détectée.</p>}
            {alertes?.entreprises_en_retard.map((enterprise) => <div key={enterprise.entreprise_id} className="flex items-center justify-between gap-3 border-b px-5 py-3 last:border-0"><div><p className="text-sm font-semibold">{enterprise.entreprise_nom}</p><p className="text-xs text-slate-500">{Math.round(enterprise.jours_de_retard)} jour(s) de retard • dernier envoi il y a {Math.round(enterprise.jours_depuis_dernier_upload)} jour(s)</p></div><button type="button" onClick={() => createReminder(enterprise.entreprise_id, enterprise.entreprise_nom)} className="shrink-0 rounded-lg border border-orange-300 px-3 py-1.5 text-xs font-semibold text-orange-700 hover:bg-orange-50">Créer une relance</button></div>)}
          </section>

          <section className="overflow-hidden rounded-xl border border-green-200 bg-white shadow-sm">
            <div className="border-b bg-green-50 px-5 py-4"><h2 className="flex items-center gap-2 font-bold text-green-900"><FileText size={18} /> Validées mais non saisies</h2><p className="text-xs text-green-700">Écritures prêtes qui restent à reporter dans Topaze.</p></div>
            {loadingAlerts && <p className="p-5 text-sm text-slate-400">Chargement...</p>}
            {!loadingAlerts && (!alertes || alertes.non_saisies.length === 0) && <p className="p-5 text-sm text-slate-400">Toutes les écritures validées sont saisies.</p>}
            {alertes?.non_saisies.map((item) => <div key={item.id} className="flex items-center justify-between gap-3 border-b px-5 py-3 last:border-0"><button type="button" onClick={() => navigate(`/documents/${item.document_id}`)} className="min-w-0 text-left"><p className="truncate text-sm font-semibold">{item.tiers ?? "Tiers inconnu"} {item.numero_piece ? `• ${item.numero_piece}` : ""}</p><p className="truncate text-xs text-slate-500">{item.entreprise_nom} • {item.nom_fichier_document} • {formatMoney(item.montant_ttc)}</p></button><button type="button" disabled={busyId === item.id} onClick={() => void markEntryDone(item.id)} className="shrink-0 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50">Marquer saisie</button></div>)}
          </section>
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="font-bold text-slate-900">Plan de travail</h2><p className="text-xs text-slate-500">Organisez les actions par statut et contrôlez les échéances.</p></div>
              <div className="inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1" aria-label="Mode d'affichage">
                <button type="button" onClick={() => setViewMode("board")} className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold ${viewMode === "board" ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500"}`}><Columns3 size={15} /> Tableau</button>
                <button type="button" onClick={() => setViewMode("list")} className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold ${viewMode === "list" ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500"}`}><ListTodo size={15} /> Liste</button>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_260px_180px_180px_auto]">
              <div className="relative"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher une tâche..." className="w-full rounded-lg border py-2.5 pl-10 pr-3 text-sm" /></div>
              <select value={entrepriseId} onChange={(event) => setEntrepriseId(event.target.value)} className="rounded-lg border px-3 py-2.5 text-sm"><option value="">Toutes les entreprises</option>{entreprises.map((enterprise) => <option key={enterprise.id} value={enterprise.id}>{enterprise.nom}</option>)}</select>
              <select value={statut} onChange={(event) => setStatut(event.target.value as StatutTache | "")} className="rounded-lg border px-3 py-2.5 text-sm"><option value="">Tous les statuts</option><option value="a_faire">À faire</option><option value="en_cours">En cours</option><option value="terminee">Terminée</option></select>
              <select value={priorite} onChange={(event) => setPriorite(event.target.value as PrioriteTache | "")} className="rounded-lg border px-3 py-2.5 text-sm"><option value="">Toutes les priorités</option><option value="basse">Basse</option><option value="normale">Normale</option><option value="haute">Haute</option></select>
              <label className="flex items-center gap-2 rounded-lg border px-3 text-sm"><input type="checkbox" checked={onlyLate} onChange={(event) => setOnlyLate(event.target.checked)} className="accent-red-600" /> En retard</label>
            </div>
          </div>

          <div className="bg-slate-50/70 p-4">
            {loading && <p className="p-8 text-center text-sm text-slate-400">Chargement...</p>}
            {!loading && visibleTasks.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center"><ListTodo className="mx-auto mb-3 text-slate-300" size={32} /><p className="font-semibold text-slate-600">Aucune tâche pour ces filtres</p><p className="mt-1 text-xs text-slate-400">Modifiez les filtres ou créez une nouvelle tâche.</p></div>}
            {!loading && visibleTasks.length > 0 && viewMode === "board" && (
              <div className="grid gap-4 xl:grid-cols-3">
                {(["a_faire", "en_cours", "terminee"] as StatutTache[]).map((columnStatus) => {
                  const columnTasks = visibleTasks.filter((task) => task.statut === columnStatus);
                  return <section key={columnStatus} className="min-w-0 rounded-xl border border-slate-200 bg-slate-100/80 p-3"><div className="mb-3 flex items-center justify-between px-1"><h3 className="text-sm font-bold text-slate-700">{STATUS_LABELS[columnStatus]}</h3><span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-slate-500 shadow-sm">{columnTasks.length}</span></div><div className="space-y-3">{columnTasks.length === 0 && <p className="rounded-lg border border-dashed border-slate-300 bg-white/60 px-3 py-6 text-center text-xs text-slate-400">Aucune tâche</p>}{columnTasks.map((task) => <article key={task.id} className={`rounded-xl border bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${task.est_en_retard ? "border-red-200 border-l-4 border-l-red-500" : task.priorite === "haute" ? "border-l-4 border-l-amber-500" : "border-slate-200"}`}><div className="mb-2 flex items-start justify-between gap-2"><h4 className="text-sm font-bold leading-snug text-slate-900">{task.titre}</h4><button type="button" disabled={busyId === task.id} onClick={() => void removeTask(task.id)} className="shrink-0 rounded-md p-1 text-slate-300 hover:bg-red-50 hover:text-red-600" aria-label={`Supprimer ${task.titre}`}><Trash2 size={14} /></button></div>{task.description && <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-slate-500">{task.description}</p>}<div className="mb-3 flex flex-wrap gap-1.5"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${PRIORITY_CLASSES[task.priorite]}`}>{task.priorite}</span>{task.recurrence !== "aucune" && <span className="rounded-full bg-purple-100 px-2 py-1 text-[10px] font-bold text-purple-700">{RECURRENCE_LABELS[task.recurrence]}</span>}</div><div className={`rounded-lg px-2.5 py-2 text-xs font-semibold ${task.est_en_retard ? "bg-red-50 text-red-700" : "bg-slate-50 text-slate-600"}`}><CalendarClock className="mr-1.5 inline" size={14} />{dueLabel(task)}</div><p className="mt-2 truncate text-[11px] text-slate-400">{task.entreprise_nom ?? "Cabinet"}{task.assignee_nom ? ` • ${task.assignee_nom}` : ""}</p><div className="mt-3 flex gap-2">{task.statut === "a_faire" && <button type="button" disabled={busyId === task.id} onClick={() => void changeStatus(task, "en_cours")} className="flex-1 rounded-lg border border-blue-200 px-2 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50">Démarrer</button>}{task.statut !== "terminee" && <button type="button" disabled={busyId === task.id} onClick={() => void changeStatus(task, "terminee")} className="flex-1 rounded-lg bg-emerald-600 px-2 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700">Terminer</button>}</div></article>)}</div></section>;
                })}
              </div>
            )}
            {!loading && visibleTasks.length > 0 && viewMode === "list" && <div className="space-y-3">{visibleTasks.map((task) => <article key={task.id} className={`rounded-xl border bg-white p-4 shadow-sm ${task.est_en_retard ? "border-red-200 border-l-4 border-l-red-500" : "border-slate-200"}`}><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><div className="mb-2 flex flex-wrap items-center gap-2"><h3 className="font-semibold text-slate-900">{task.titre}</h3><span className={`rounded-full px-2 py-1 text-xs font-semibold ${STATUS_CLASSES[task.statut]}`}>{STATUS_LABELS[task.statut]}</span><span className={`rounded-full px-2 py-1 text-xs font-semibold ${PRIORITY_CLASSES[task.priorite]}`}>{task.priorite}</span></div>{task.description && <p className="mb-2 text-sm text-slate-600">{task.description}</p>}<p className={`text-xs font-medium ${task.est_en_retard ? "text-red-600" : "text-slate-500"}`}>{dueLabel(task)} • {task.entreprise_nom ?? "Cabinet"}{task.assignee_nom ? ` • ${task.assignee_nom}` : ""}</p></div><div className="flex shrink-0 flex-wrap gap-2">{task.statut === "a_faire" && <button type="button" disabled={busyId === task.id} onClick={() => void changeStatus(task, "en_cours")} className="rounded-lg border border-blue-200 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50">Démarrer</button>}{task.statut !== "terminee" && <button type="button" disabled={busyId === task.id} onClick={() => void changeStatus(task, "terminee")} className="inline-flex items-center gap-1 rounded-lg border border-green-200 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"><CheckCircle2 size={14} /> Terminer</button>}<button type="button" disabled={busyId === task.id} onClick={() => void removeTask(task.id)} className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"><Trash2 size={14} /> Supprimer</button></div></div></article>)}</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
