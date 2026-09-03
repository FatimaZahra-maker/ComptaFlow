import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { BarChart3, RefreshCw, TriangleAlert } from "lucide-react";

import { getCpc } from "../api/cpcApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { Cpc, CpcCompteDetail } from "../types/cpc";
import type { Entreprise } from "../types/entreprise";

function money(value: string | number | null | undefined): string {
  const parsed = Number(value ?? 0);
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "MAD",
  }).format(Number.isFinite(parsed) ? parsed : 0);
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

const RUBRIQUE_LABELS: Record<string, string> = {
  produits_exploitation: "Produits d'exploitation",
  charges_exploitation: "Charges d'exploitation",
  produits_financiers: "Produits financiers",
  charges_financieres: "Charges financières",
  produits_non_courants: "Produits non courants",
  charges_non_courantes: "Charges non courantes",
  impots_sur_resultats: "Impôts sur les résultats",
  non_classee: "À classer",
};

function ComparisonRow({ item, strong = false }: { item: Cpc["rubriques"][number]; strong?: boolean }) {
  const amount = Number(item.montant_n ?? 0);
  return (
    <tr className={`border-t ${strong ? "bg-gray-50 font-bold" : ""}`}>
      <td className="px-4 py-3">{item.libelle}</td>
      <td className={`px-4 py-3 text-right ${amount < 0 ? "text-red-600" : ""}`}>{money(item.montant_n)}</td>
      <td className="px-4 py-3 text-right">{item.montant_n_1 === null ? "Non disponible" : money(item.montant_n_1)}</td>
      <td className="px-4 py-3 text-right">{item.variation_mad === null ? "—" : money(item.variation_mad)}</td>
      <td className="px-4 py-3 text-right">{item.variation_pct === null ? "—" : `${item.variation_pct} %`}</td>
    </tr>
  );
}

export function CpcPage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const [data, setData] = useState<Cpc | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    listAvailableEntreprises("cpc", annee)
      .then((items) => {
        setEntreprises(items);
        const active = localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
        setEntrepriseId((current) => chooseAvailableEntreprise(items, current, active));
      })
      .catch((err) => setError(errorMessage(err)));
  }, [annee]);

  const load = useCallback(async () => {
    if (!entrepriseId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await getCpc({ entreprise_id: entrepriseId, annee }));
    } catch (err) {
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, annee]);

  useEffect(() => { void load(); }, [load]);

  const comptesParRubrique = useMemo(() => {
    const groups = new Map<string, CpcCompteDetail[]>();
    for (const item of data?.comptes ?? []) {
      const values = groups.get(item.rubrique) ?? [];
      values.push(item);
      groups.set(item.rubrique, values);
    }
    return [...groups.entries()];
  }, [data]);

  return (
    <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1400px]">
        <header className="mb-6">
          <div className="flex items-center gap-2 text-indigo-700">
            <BarChart3 size={22} />
            <span className="text-sm font-semibold">États de synthèse</span>
          </div>
          <h1 className="mt-1 text-3xl font-bold text-gray-950">Compte de Produits et Charges</h1>
          <p className="mt-1 text-sm text-gray-500">CPC provisoire de contrôle, calculé exclusivement depuis les lignes comptables admissibles du Grand Livre en MAD. Il ne remplace pas l’état officiel produit dans Topaze.</p>
        </header>

        <section className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm md:grid-cols-[1fr_180px_auto]">
          <label className="text-sm font-medium text-gray-700">
            Entreprise
            <select value={entrepriseId} onChange={(e) => setEntrepriseId(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
              <option value="">Sélectionner</option>
              {entreprises.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">
            Exercice
            <input type="number" min={2000} max={2100} value={annee} onChange={(e) => setAnnee(Number(e.target.value))} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <button type="button" onClick={() => void load()} className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-gray-950 px-4 text-sm font-semibold text-white">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Actualiser
          </button>
        </section>

        {entreprises.length === 0 && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise ne possède encore de données dans ce module.</div>}

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        {data?.statut === "a_verifier" && (
          <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <div className="mb-2 flex items-center gap-2 font-bold"><TriangleAlert size={18} /> CPC à vérifier</div>
            <ul className="list-disc space-y-1 pl-5">{data.anomalies.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </section>
        )}

        <section className="mb-5 overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
          <div className="border-b px-5 py-4"><h2 className="font-bold">CPC comparatif</h2><p className="text-xs text-gray-500">N-1 reste absent lorsqu'aucune donnée n'existe.</p></div>
          <div className="overflow-x-auto"><table className="w-full min-w-[800px] text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500"><tr><th className="px-4 py-3">Rubrique</th><th className="px-4 py-3 text-right">N ({annee})</th><th className="px-4 py-3 text-right">N-1 ({annee - 1})</th><th className="px-4 py-3 text-right">Variation MAD</th><th className="px-4 py-3 text-right">Variation %</th></tr></thead>
            <tbody>{data?.rubriques.map((item) => <ComparisonRow key={item.code} item={item} />)}{data?.resultats.map((item) => <ComparisonRow key={item.code} item={item} strong />)}</tbody>
          </table></div>
        </section>

        {data && <section className="mb-5 grid gap-3 md:grid-cols-2">
          <div className={`rounded-xl border p-4 ${data.controle_grand_livre_balance.coherent ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}><p className="font-bold">Grand Livre ↔ Balance</p><p className="mt-1 text-sm">Débit {money(data.controle_grand_livre_balance.total_debit_grand_livre)} · Crédit {money(data.controle_grand_livre_balance.total_credit_grand_livre)}</p></div>
          <div className="rounded-xl border bg-white p-4"><p className="font-bold">Comptes non classés</p><p className="mt-1 text-sm text-gray-600">{data.comptes_non_classes.length} compte(s), conservés dans le détail.</p></div>
        </section>}

        <section className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b px-5 py-4">
            <div>
              <h2 className="font-bold text-gray-900">Détail par compte</h2>
              <p className="text-xs text-gray-500">{data?.nombre_comptes ?? 0} compte(s) CPC · {data?.nombre_lignes ?? 0} ligne(s) validée(s) analysée(s)</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500"><tr><th className="px-4 py-3">Rubrique</th><th className="px-4 py-3">Compte</th><th className="px-4 py-3">Libellé</th><th className="px-4 py-3 text-right">Débit</th><th className="px-4 py-3 text-right">Crédit</th><th className="px-4 py-3 text-right">Montant CPC</th></tr></thead>
              <tbody>
                {loading && <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400">Chargement…</td></tr>}
                {!loading && comptesParRubrique.flatMap(([rubrique, comptes]) => comptes.map((item) => (
                  <tr key={`${rubrique}-${item.compte}`} className="border-t border-gray-100">
                    <td className="px-4 py-3">{RUBRIQUE_LABELS[rubrique] ?? rubrique}</td>
                    <td className="px-4 py-3 font-semibold">{item.compte}</td>
                    <td className="px-4 py-3">{item.libelle_compte ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{money(item.debit)}</td>
                    <td className="px-4 py-3 text-right">{money(item.credit)}</td>
                    <td className="px-4 py-3 text-right font-semibold">{money(item.montant)}</td>
                  </tr>
                )))}
                {!loading && (!data || data.comptes.length === 0) && <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400">Aucun compte de classe 6 ou 7 validé pour cet exercice.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
