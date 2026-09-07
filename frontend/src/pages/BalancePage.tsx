import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { RefreshCw, Scale } from "lucide-react";

import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { getBalance } from "../api/ledgerApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { Entreprise } from "../types/entreprise";
import type { Balance } from "../types/ledger";

function money(value: string | number | null | undefined): string {
  const parsed = Number(value ?? 0);
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "MAD" }).format(Number.isFinite(parsed) ? parsed : 0);
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible.";
    return `Erreur API ${error.response.status}.`;
  }
  return "Erreur inattendue.";
}

export function BalancePage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");
  const [data, setData] = useState<Balance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAvailableEntreprises("balance").then((items) => {
      setEntreprises(items);
      const active = localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
      setEntrepriseId((current) => chooseAvailableEntreprise(items, current, active));
    }).catch((err) => setError(errorMessage(err)));
  }, []);

  const load = useCallback(async () => {
    if (!entrepriseId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await getBalance({
        entreprise_id: entrepriseId,
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
      }));
    } catch (err) {
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, dateDebut, dateFin]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1400px]">
        <div className="mb-6">
          <div className="flex items-center gap-2 text-emerald-700"><Scale size={22} /><span className="text-sm font-semibold">Contrôle comptable</span></div>
          <h1 className="mt-1 text-3xl font-bold text-gray-950">Balance</h1>
          <p className="mt-1 text-sm text-gray-500">Totaux Débit / Crédit et soldes par compte.</p>
        </div>

        <section className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm md:grid-cols-3">
          <label className="text-sm font-medium text-gray-700">Entreprise<select value={entrepriseId} onChange={(e) => setEntrepriseId(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"><option value="">Sélectionner</option>{entreprises.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}</select></label>
          <label className="text-sm font-medium text-gray-700">Du<input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" /></label>
          <label className="text-sm font-medium text-gray-700">Au<input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" /></label>
        </section>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        {entreprises.length === 0 && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise gérée et active n’est disponible dans ce cabinet.</div>}
        {data && data.anomalies.length > 0 && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><p className="font-bold">Contrôles complémentaires</p><ul className="mt-2 list-disc pl-5">{data.anomalies.map((item) => <li key={item}>{item}</li>)}</ul><p className="mt-2 text-xs">Une balance équilibrée ne prouve pas que les comptes, tiers, périodes et pièces sont tous corrects.</p></div>}

        <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Comptes</p><p className="mt-1 text-2xl font-bold">{data?.nombre_comptes ?? 0}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Débit</p><p className="mt-1 font-bold">{money(data?.total_debit)}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Crédit</p><p className="mt-1 font-bold">{money(data?.total_credit)}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Soldes débiteurs</p><p className="mt-1 font-bold">{money(data?.total_solde_debiteur)}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Contrôle</p><p className={`mt-1 font-bold ${data?.equilibree ? "text-emerald-600" : "text-red-600"}`}>{data?.equilibree ? "Équilibrée" : "À contrôler"}</p></div>
        </section>

        <section className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b px-5 py-4"><h2 className="font-bold text-gray-900">Balance des comptes</h2><button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600"><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Actualiser</button></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[950px] text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500"><tr><th className="px-4 py-3">Compte</th><th className="px-4 py-3">Libellé</th><th className="px-4 py-3 text-right">Débit</th><th className="px-4 py-3 text-right">Crédit</th><th className="px-4 py-3 text-right">Solde débiteur</th><th className="px-4 py-3 text-right">Solde créditeur</th></tr></thead>
              <tbody>
                {loading && <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400">Chargement…</td></tr>}
                {!loading && data?.lignes.map((line) => <tr key={line.compte} className="border-t border-gray-100"><td className="px-4 py-3 font-semibold">{line.compte}</td><td className="px-4 py-3">{line.libelle_compte ?? "—"}</td><td className="px-4 py-3 text-right">{money(line.total_debit)}</td><td className="px-4 py-3 text-right">{money(line.total_credit)}</td><td className="px-4 py-3 text-right">{Number(line.solde_debiteur) ? money(line.solde_debiteur) : "—"}</td><td className="px-4 py-3 text-right">{Number(line.solde_crediteur) ? money(line.solde_crediteur) : "—"}</td></tr>)}
                {!loading && (!data || data.lignes.length === 0) && <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400">Aucune ligne validée pour cette période.</td></tr>}
              </tbody>
              {data && data.lignes.length > 0 && <tfoot className="border-t-2 bg-gray-50 font-bold"><tr><td colSpan={2} className="px-4 py-3">TOTAL</td><td className="px-4 py-3 text-right">{money(data.total_debit)}</td><td className="px-4 py-3 text-right">{money(data.total_credit)}</td><td className="px-4 py-3 text-right">{money(data.total_solde_debiteur)}</td><td className="px-4 py-3 text-right">{money(data.total_solde_crediteur)}</td></tr></tfoot>}
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
