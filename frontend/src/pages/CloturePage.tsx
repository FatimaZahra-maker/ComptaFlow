import { useCallback, useEffect, useState, type FormEvent } from "react";
import axios from "axios";
import { CalendarCheck, Plus, RefreshCw } from "lucide-react";

import {
  createRegularisationCloture, generateRegularisationCloture,
  listRegularisationsCloture, validateRegularisationCloture,
} from "../api/clotureApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { Entreprise } from "../types/entreprise";
import { listWorkPeriods, lockWorkPeriod, reopenWorkPeriod } from "../api/workflowComptableApi";
import type { WorkPeriod } from "../types/workflowComptable";
import type { RegularisationCloture, TypeRegularisationCloture } from "../types/cloture";

const TYPES: Array<[TypeRegularisationCloture, string]> = [
  ["amortissement", "Amortissement"], ["provision", "Provision"], ["stock", "Stock"],
  ["charge_constatee_avance", "Charge constatee d'avance"],
  ["produit_constate_avance", "Produit constate d'avance"],
  ["charge_a_payer", "Charge a payer"], ["produit_a_recevoir", "Produit a recevoir"],
  ["ajustement_manuel", "Autre ajustement manuel"],
  ["resultat_cloture", "Resultat de cloture"], ["report_a_nouveau", "Report a nouveau"],
];

function message(error: unknown) {
  if (axios.isAxiosError(error)) return String(error.response?.data?.detail ?? "Backend inaccessible.");
  return "Erreur inattendue.";
}

function money(value: string) {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "MAD" }).format(Number(value));
}

export function CloturePage() {
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [periods, setPeriods] = useState<WorkPeriod[]>([]);
  const [exercice, setExercice] = useState(new Date().getFullYear());
  const [items, setItems] = useState<RegularisationCloture[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    type: "ajustement_manuel" as TypeRegularisationCloture, libelle: "", montant: "",
    debit: "", credit: "", date: `${new Date().getFullYear()}-12-31`,
  });

  useEffect(() => {
    setItems([]);
    listAvailableEntreprises("cloture", exercice).then((values) => {
      setCompanies(values);
      const active = localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
      setEntrepriseId((current) => chooseAvailableEntreprise(values, current, active));
    }).catch((reason) => setError(message(reason)));
  }, [exercice]);

  const load = useCallback(async () => {
    if (!entrepriseId) return;
    setLoading(true); setError(null);
    try {
      const [regularisations, workPeriods] = await Promise.all([listRegularisationsCloture(entrepriseId, exercice), listWorkPeriods(entrepriseId, exercice)]);
      setItems(regularisations); setPeriods(workPeriods);
    }
    catch (reason) { setError(message(reason)); }
    finally { setLoading(false); }
  }, [entrepriseId, exercice]);

  async function lockYear() {
    if (!entrepriseId) return;
    try {
      await lockWorkPeriod(entrepriseId, { exercice, periode_debut: `${exercice}-01-01`, periode_fin: `${exercice}-12-31` });
      await load();
    } catch (reason) { setError(message(reason)); }
  }

  async function reopen(period: WorkPeriod) {
    const justification = window.prompt("Justification obligatoire de la réouverture");
    if (!justification) return;
    try { await reopenWorkPeriod(entrepriseId, period.id, justification); await load(); }
    catch (reason) { setError(message(reason)); }
  }

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setForm((old) => ({ ...old, date: `${exercice}-12-31` })); }, [exercice]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!entrepriseId) return;
    setError(null);
    try {
      await createRegularisationCloture(entrepriseId, {
        exercice, date_ecriture: form.date, type_regularisation: form.type,
        libelle: form.libelle, montant: Number(form.montant),
        compte_debit: form.debit || undefined, compte_credit: form.credit || undefined,
      });
      setForm((old) => ({ ...old, libelle: "", montant: "", debit: "", credit: "" }));
      await load();
    } catch (reason) { setError(message(reason)); }
  }

  async function act(item: RegularisationCloture, action: "validate" | "generate") {
    try {
      if (action === "validate") await validateRegularisationCloture(entrepriseId, item.id);
      else await generateRegularisationCloture(entrepriseId, item.id);
      await load();
    } catch (reason) { setError(message(reason)); }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="mb-6 flex items-start justify-between">
          <div><div className="flex items-center gap-2 text-emerald-700"><CalendarCheck size={22} /><span className="text-sm font-semibold">Comptabilité</span></div><h1 className="mt-1 text-3xl font-bold">Clôture de travail ComptaFlow</h1><p className="mt-1 text-sm text-slate-500">Contrôle et verrouillage interne de la période. Cette action ne remplace pas la clôture officielle dans Topaze.</p></div>
          <button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-semibold"><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Actualiser</button>
        </div>

        <section className="mb-5 grid gap-3 rounded-xl border bg-white p-4 shadow-sm md:grid-cols-2">
          <label className="text-sm font-medium">Entreprise<select value={entrepriseId} onChange={(event) => setEntrepriseId(event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2"><option value="">Sélectionner</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.nom}</option>)}</select></label>
          <label className="text-sm font-medium">Exercice<input type="number" min={2000} max={2100} value={exercice} onChange={(event) => setExercice(Number(event.target.value))} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
        </section>

        {companies.length === 0 && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise ne possède encore de données dans ce module.</div>}

        <form onSubmit={submit} className="mb-5 grid gap-3 rounded-xl border bg-white p-4 shadow-sm md:grid-cols-3 lg:grid-cols-6">
          <select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as TypeRegularisationCloture })} className="rounded-lg border px-3 py-2">{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <input required placeholder="Libelle" value={form.libelle} onChange={(event) => setForm({ ...form, libelle: event.target.value })} className="rounded-lg border px-3 py-2" />
          <input required type="number" min="0.01" step="0.01" placeholder="Montant MAD" value={form.montant} onChange={(event) => setForm({ ...form, montant: event.target.value })} className="rounded-lg border px-3 py-2" />
          <input placeholder="Compte debit exact" value={form.debit} onChange={(event) => setForm({ ...form, debit: event.target.value })} className="rounded-lg border px-3 py-2" />
          <input placeholder="Compte credit exact" value={form.credit} onChange={(event) => setForm({ ...form, credit: event.target.value })} className="rounded-lg border px-3 py-2" />
          <button className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 font-semibold text-white"><Plus size={16} />Ajouter</button>
        </form>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <section className="mb-5 rounded-xl border bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">Verrouillage de l’exercice</h2><p className="text-xs text-slate-500">Le verrouillage est refusé si la pré-clôture contient un blocage.</p></div><button type="button" disabled={!entrepriseId || periods.some((period) => period.verrouillee)} onClick={() => void lockYear()} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Verrouiller dans ComptaFlow</button></div>
          {periods.map((period) => <div key={period.id} className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm"><span>{period.periode_debut} — {period.periode_fin}</span><span className={`rounded-full px-2 py-1 text-xs font-bold ${period.verrouillee ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{period.verrouillee ? "Verrouillée" : "Ouverte"}</span>{period.verrouillee && <button type="button" onClick={() => void reopen(period)} className="rounded border px-3 py-1.5 text-xs font-semibold">Réouvrir avec justification</button>}</div>)}
        </section>
        <section className="overflow-hidden rounded-xl border bg-white shadow-sm">
          <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Date / type</th><th className="px-4 py-3">Libelle</th><th className="px-4 py-3 text-right">Montant</th><th className="px-4 py-3">Debit</th><th className="px-4 py-3">Credit</th><th className="px-4 py-3">Statut / anomalies</th><th className="px-4 py-3">Actions</th></tr></thead>
          <tbody>{items.map((item) => <tr key={item.id} className="border-t align-top"><td className="px-4 py-3"><div>{item.date_ecriture}</div><div className="text-xs text-slate-500">{TYPES.find(([value]) => value === item.type_regularisation)?.[1]}</div></td><td className="px-4 py-3">{item.libelle}</td><td className="px-4 py-3 text-right font-semibold">{money(item.montant)}</td><td className="px-4 py-3 font-mono">{item.compte_debit ?? "A verifier"}</td><td className="px-4 py-3 font-mono">{item.compte_credit ?? "A verifier"}</td><td className="px-4 py-3"><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">{item.statut}</span>{item.anomalies.map((anomaly) => <div key={anomaly} className="mt-1 text-xs text-amber-700">{anomaly}</div>)}</td><td className="px-4 py-3"><div className="flex gap-2">{["brouillon", "a_verifier"].includes(item.statut) && <button type="button" onClick={() => void act(item, "validate")} className="rounded border px-2 py-1 text-xs font-semibold">Valider</button>}{item.statut === "validee" && <button type="button" onClick={() => void act(item, "generate")} className="rounded bg-emerald-700 px-2 py-1 text-xs font-semibold text-white">Generer</button>}</div></td></tr>)}</tbody>
          </table>{!loading && items.length === 0 && <p className="p-10 text-center text-slate-400">Aucune regularisation pour cet exercice.</p>}</div>
        </section>
      </div>
    </div>
  );
}
