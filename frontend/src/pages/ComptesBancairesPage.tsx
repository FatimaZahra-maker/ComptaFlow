import { useEffect, useMemo, useState, type FormEvent } from "react";
import axios from "axios";
import { Building2, Landmark, Plus, Trash2 } from "lucide-react";

import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { getActiveEntrepriseId } from "../utils/activeEntreprise";
import {
  createBankAccount,
  deactivateBankAccount,
  listBankAccounts,
} from "../api/accountingApi";
import type { Entreprise } from "../types/entreprise";
import type {
  CompteBancaireCreate,
  CompteBancaireEntreprise,
} from "../types/mouvementBancaire";

function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Une erreur inattendue s’est produite.";
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (!error.response) return "Backend inaccessible.";
  return `Erreur API ${error.response.status}.`;
}

export function ComptesBancairesPage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [accounts, setAccounts] = useState<CompteBancaireEntreprise[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<CompteBancaireCreate>({
    entreprise_id: "",
    libelle: "",
    banque_nom: "",
    rib: "",
    iban: "",
    bic_swift: "",
    devise: "MAD",
    numero_compte_comptable: "",
  });

  useEffect(() => {
    listAvailableEntreprises("comptes_bancaires")
      .then((rows) => {
        setEntreprises(rows);
        setEntrepriseId((value) => chooseAvailableEntreprise(rows, value, getActiveEntrepriseId()));
      })
      .catch(() => setEntreprises([]));
  }, []);

  useEffect(() => {
    if (!entrepriseId) {
      setAccounts([]);
      return;
    }
    setForm((current) => ({ ...current, entreprise_id: entrepriseId }));
    setLoading(true);
    setError(null);
    listBankAccounts(entrepriseId)
      .then(setAccounts)
      .catch((requestError) => setError(errorMessage(requestError)))
      .finally(() => setLoading(false));
  }, [entrepriseId]);

  const entreprise = useMemo(
    () => entreprises.find((item) => item.id === entrepriseId),
    [entreprises, entrepriseId],
  );

  async function refresh(): Promise<void> {
    if (!entrepriseId) return;
    setAccounts(await listBankAccounts(entrepriseId));
  }

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!entrepriseId) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await createBankAccount({
        ...form,
        entreprise_id: entrepriseId,
        banque_nom: form.banque_nom?.trim() || null,
        rib: form.rib?.trim() || null,
        iban: form.iban?.trim() || null,
        bic_swift: form.bic_swift?.trim() || null,
        devise: (form.devise || "MAD").trim().toUpperCase(),
        libelle: form.libelle.trim(),
        numero_compte_comptable: form.numero_compte_comptable.trim(),
      });
      setForm({
        entreprise_id: entrepriseId,
        libelle: "",
        banque_nom: "",
        rib: "",
        iban: "",
        bic_swift: "",
        devise: "MAD",
        numero_compte_comptable: "",
      });
      setSuccess("Compte bancaire ajouté.");
      await refresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(id: string): Promise<void> {
    if (!window.confirm("Désactiver ce compte bancaire ?")) return;
    try {
      await deactivateBankAccount(id);
      await refresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 p-5 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-green-700">Banque V2</p>
            <h1 className="mt-1 text-2xl font-black text-slate-900">Comptes bancaires de l’entreprise</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              RIB/IBAN servent à identifier le compte du relevé. Le numéro comptable doit déjà exister dans le plan comptable exact de l’entreprise.
            </p>
          </div>
          <label className="min-w-64 text-sm font-semibold text-slate-700">
            Entreprise
            <select
              value={entrepriseId}
              onChange={(event) => setEntrepriseId(event.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
            >
              <option value="">Sélectionner</option>
              {entreprises.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}
            </select>
            {entreprises.length === 0 && <p className="mt-2 text-xs text-amber-700">Aucune entreprise ne possède encore de données dans ce module.</p>}
          </label>
        </header>

        {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center gap-3 border-b px-5 py-4">
              <Landmark className="text-green-700" size={20} />
              <div>
                <h2 className="font-bold text-slate-900">{entreprise?.nom ?? "Entreprise"}</h2>
                <p className="text-xs text-slate-500">{accounts.length} compte(s) bancaire(s) actif(s)</p>
              </div>
            </div>
            <div className="divide-y divide-slate-100">
              {loading && <p className="p-6 text-center text-sm text-slate-400">Chargement...</p>}
              {!loading && accounts.map((account) => (
                <div key={account.id} className="flex items-start justify-between gap-4 p-5">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong>{account.libelle}</strong>
                      <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-bold text-green-700">{account.devise}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{account.banque_nom || "Banque non précisée"}</p>
                    <div className="mt-2 space-y-1 text-xs text-slate-500">
                      <p>Compte comptable : <span className="font-mono font-bold text-slate-800">{account.numero_compte_comptable}</span></p>
                      <p>RIB : {account.rib || "—"}</p>
                      <p>IBAN : {account.iban || "—"}</p>
                    </div>
                  </div>
                  <button type="button" onClick={() => void deactivate(account.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="Désactiver">
                    <Trash2 size={17} />
                  </button>
                </div>
              ))}
              {!loading && accounts.length === 0 && (
                <div className="p-10 text-center text-slate-400"><Building2 className="mx-auto mb-2" />Aucun compte bancaire configuré.</div>
              )}
            </div>
          </section>

          <form onSubmit={(event) => void submit(event)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center gap-2"><Plus size={19} className="text-green-700" /><h2 className="font-bold">Ajouter un compte bancaire</h2></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium sm:col-span-2">Libellé *<input required value={form.libelle} onChange={(e) => setForm({ ...form, libelle: e.target.value })} placeholder="Attijariwafa - compte principal" className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
              <label className="text-sm font-medium">Banque<input value={form.banque_nom ?? ""} onChange={(e) => setForm({ ...form, banque_nom: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label>
              <label className="text-sm font-medium">Devise<input value={form.devise ?? "MAD"} onChange={(e) => setForm({ ...form, devise: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2 uppercase" /></label>
              <label className="text-sm font-medium sm:col-span-2">Compte comptable exact *<input required value={form.numero_compte_comptable} onChange={(e) => setForm({ ...form, numero_compte_comptable: e.target.value })} placeholder="Compte déjà présent dans le plan" className="mt-1 w-full rounded-lg border px-3 py-2 font-mono" /></label>
              <label className="text-sm font-medium sm:col-span-2">RIB<input value={form.rib ?? ""} onChange={(e) => setForm({ ...form, rib: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2 font-mono" /></label>
              <label className="text-sm font-medium sm:col-span-2">IBAN<input value={form.iban ?? ""} onChange={(e) => setForm({ ...form, iban: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2 font-mono" /></label>
              <label className="text-sm font-medium sm:col-span-2">BIC / SWIFT<input value={form.bic_swift ?? ""} onChange={(e) => setForm({ ...form, bic_swift: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2 font-mono" /></label>
            </div>
            <button disabled={saving || !entrepriseId} className="mt-5 w-full rounded-xl bg-green-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-green-700 disabled:opacity-50">{saving ? "Enregistrement..." : "Ajouter le compte"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
