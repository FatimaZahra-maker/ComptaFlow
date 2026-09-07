import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import axios from "axios";
import { BookOpen, Plus, Search, Trash2 } from "lucide-react";

import { createPlanAccount, deactivatePlanAccount, listPlanAccounts } from "../api/planComptableApi";
import { listEntreprises } from "../api/entreprisesApi";
import { getActiveEntrepriseId, setActiveEntrepriseId } from "../utils/activeEntreprise";
import type { Entreprise } from "../types/entreprise";
import type { CompteComptableCreate, CompteComptableEntreprise, TypeUsageCompte } from "../types/planComptable";

const USAGE_LABELS: Record<TypeUsageCompte, string> = {
  ht: "HT (charge/produit)", tva: "TVA", fournisseur: "Fournisseur", client: "Client",
  banque: "Banque", gain_change: "Gain de change", perte_change: "Perte de change", autre: "Autre",
};

const EMPTY_FORM: CompteComptableCreate = { numero_compte: "", libelle: "", famille_cgnc: "", type_usage: "ht", nature_comptable: "", tiers_nom: "", est_divers: false, is_active: true };

function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Une erreur inattendue s’est produite.";
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : error.response ? `Erreur API ${error.response.status}.` : "Backend inaccessible.";
}

export function PlanComptablePage() {
  const [searchParams] = useSearchParams();
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState(searchParams.get("entreprise_id") ?? getActiveEntrepriseId() ?? "");
  const [accounts, setAccounts] = useState<CompteComptableEntreprise[]>([]);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState<CompteComptableCreate>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    listEntreprises().then((rows) => {
      setEntreprises(rows);
      if (!entrepriseId && rows[0]) setEntrepriseId(rows[0].id);
    }).catch((requestError) => setError(errorMessage(requestError)));
  }, [entrepriseId]);

  useEffect(() => {
    if (!entrepriseId) { setAccounts([]); return; }
    setActiveEntrepriseId(entrepriseId);
    setLoading(true);
    setError(null);
    listPlanAccounts(entrepriseId).then(setAccounts).catch((requestError) => setError(errorMessage(requestError))).finally(() => setLoading(false));
  }, [entrepriseId]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("fr");
    return normalized ? accounts.filter((account) => `${account.numero_compte} ${account.libelle} ${account.tiers_nom ?? ""}`.toLocaleLowerCase("fr").includes(normalized)) : accounts;
  }, [accounts, query]);

  async function refresh() { if (entrepriseId) setAccounts(await listPlanAccounts(entrepriseId)); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!entrepriseId) return;
    setSaving(true); setError(null); setSuccess(null);
    try {
      await createPlanAccount(entrepriseId, { ...form, numero_compte: form.numero_compte.trim(), libelle: form.libelle.trim(), famille_cgnc: form.famille_cgnc?.trim() || null, nature_comptable: form.nature_comptable?.trim() || null, tiers_nom: form.tiers_nom?.trim() || null });
      setForm(EMPTY_FORM); setSuccess("Compte ajouté au plan comptable."); await refresh();
    } catch (requestError) { setError(errorMessage(requestError)); } finally { setSaving(false); }
  }

  async function deactivate(account: CompteComptableEntreprise) {
    if (!window.confirm(`Désactiver le compte ${account.numero_compte} ?`)) return;
    try { await deactivatePlanAccount(entrepriseId, account.id); await refresh(); }
    catch (requestError) { setError(errorMessage(requestError)); }
  }

  return <div className="min-h-screen bg-slate-50 p-5 lg:p-8"><div className="mx-auto max-w-7xl space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-700">Paramétrage comptable</p><h1 className="mt-1 text-2xl font-black text-slate-900">Plan comptable de l’entreprise</h1><p className="mt-1 text-sm text-slate-500">Ces comptes exacts sont utilisés pour contrôler et valider les écritures.</p></div><label className="min-w-64 text-sm font-semibold text-slate-700">Entreprise<select value={entrepriseId} onChange={(event) => setEntrepriseId(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2"><option value="">Sélectionner</option>{entreprises.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select></label></header>
    {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}{success && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{success}</div>}
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]"><section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3 border-b p-5"><div className="flex items-center gap-2"><BookOpen className="text-blue-700" size={20}/><strong>{accounts.length} compte(s) actif(s)</strong></div><label className="relative"><Search className="absolute left-3 top-2.5 text-slate-400" size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Rechercher" className="rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm"/></label></div><div className="max-h-[620px] divide-y overflow-y-auto">{loading && <p className="p-6 text-center text-sm text-slate-400">Chargement…</p>}{!loading && filtered.map((account) => <div key={account.id} className="flex items-center justify-between gap-4 p-4"><div><p className="font-mono font-bold text-slate-900">{account.numero_compte}</p><p className="text-sm text-slate-600">{account.libelle}</p><span className="mt-1 inline-block rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">{USAGE_LABELS[account.type_usage]}</span></div><button type="button" onClick={() => void deactivate(account)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="Désactiver"><Trash2 size={17}/></button></div>)}{!loading && filtered.length === 0 && <p className="p-8 text-center text-sm text-slate-500">Aucun compte actif. Ajoutez les comptes exacts de l’entreprise.</p>}</div></section>
    <form onSubmit={(event) => void submit(event)} className="h-fit rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-900">Ajouter un compte</h2><div className="mt-4 space-y-4"><label className="block text-sm font-semibold">Numéro<input required minLength={3} value={form.numero_compte} onChange={(event) => setForm({...form, numero_compte:event.target.value})} className="mt-1 w-full rounded-lg border px-3 py-2" inputMode="numeric"/></label><label className="block text-sm font-semibold">Libellé<input required value={form.libelle} onChange={(event) => setForm({...form, libelle:event.target.value})} className="mt-1 w-full rounded-lg border px-3 py-2"/></label><label className="block text-sm font-semibold">Usage<select value={form.type_usage} onChange={(event) => setForm({...form, type_usage:event.target.value as TypeUsageCompte})} className="mt-1 w-full rounded-lg border px-3 py-2">{Object.entries(USAGE_LABELS).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>{["fournisseur","client"].includes(form.type_usage) && <label className="block text-sm font-semibold">Nom du tiers<input value={form.tiers_nom ?? ""} onChange={(event) => setForm({...form, tiers_nom:event.target.value})} className="mt-1 w-full rounded-lg border px-3 py-2"/></label>}<button disabled={!entrepriseId || saving} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 font-bold text-white disabled:opacity-50"><Plus size={17}/>{saving ? "Ajout…" : "Ajouter le compte"}</button></div></form></div>
  </div></div>;
}
