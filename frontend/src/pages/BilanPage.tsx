import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Building2,
  CheckCircle2,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";

import { getBilan } from "../api/bilanApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { Bilan, BilanCompteDetail } from "../types/bilan";
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
  actif_immobilise: "Actif immobilisé",
  amortissements_provisions_immobilisations: "Amortissements / provisions immobilisations",
  actif_circulant: "Actif circulant",
  provisions_actif_circulant: "Provisions actif circulant",
  tresorerie_actif: "Trésorerie actif",
  financement_permanent: "Financement permanent",
  passif_circulant: "Passif circulant",
  tresorerie_passif: "Trésorerie passif",
  non_classee: "À classer",
};

function SummaryRow({
  label,
  value,
  strong = false,
  subtract = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
  subtract?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-4 border-b border-gray-100 px-4 py-3 ${
        strong ? "bg-gray-50 font-bold" : ""
      }`}
    >
      <span className={subtract ? "text-gray-500" : "text-gray-800"}>
        {subtract ? `(-) ${label}` : label}
      </span>
      <span className={strong ? "font-bold text-gray-950" : "font-semibold text-gray-800"}>
        {money(value)}
      </span>
    </div>
  );
}

export function BilanPage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [annee, setAnnee] = useState(new Date().getFullYear());
  const [data, setData] = useState<Bilan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    listAvailableEntreprises("bilan", annee)
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
      setData(await getBilan({ entreprise_id: entrepriseId, annee }));
    } catch (err) {
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, annee]);

  useEffect(() => {
    void load();
  }, [load]);

  const grouped = useMemo(() => {
    const groups = new Map<string, BilanCompteDetail[]>();
    for (const item of data?.comptes ?? []) {
      const key = `${item.cote}:${item.rubrique}`;
      const values = groups.get(key) ?? [];
      values.push(item);
      groups.set(key, values);
    }
    return [...groups.entries()];
  }, [data]);

  return (
    <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-6">
          <div className="flex items-center gap-2 text-emerald-700">
            <Building2 size={22} />
            <span className="text-sm font-semibold">États de synthèse</span>
          </div>
          <h1 className="mt-1 text-3xl font-bold text-gray-950">Bilan</h1>
          <p className="mt-1 text-sm text-gray-500">
            Bilan technique construit depuis le Grand Livre validé et relié au résultat net du CPC.
          </p>
        </header>

        <section className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm md:grid-cols-[1fr_180px_auto]">
          <label className="text-sm font-medium text-gray-700">
            Entreprise
            <select
              value={entrepriseId}
              onChange={(event) => setEntrepriseId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            >
              <option value="">Sélectionner</option>
              {entreprises.map((item) => (
                <option key={item.id} value={item.id}>{item.nom}</option>
              ))}
            </select>
          </label>

          <label className="text-sm font-medium text-gray-700">
            Exercice
            <input
              type="number"
              min={2000}
              max={2100}
              value={annee}
              onChange={(event) => setAnnee(Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>

          <button
            type="button"
            onClick={() => void load()}
            className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-gray-950 px-4 text-sm font-semibold text-white"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            Actualiser
          </button>
        </section>

        {entreprises.length === 0 && <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise ne possède encore de données dans ce module.</div>}

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {data && (
          <section
            className={`mb-5 rounded-xl border p-4 ${
              data.bilan_equilibre
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 font-bold">
                {data.bilan_equilibre ? <CheckCircle2 size={19} /> : <TriangleAlert size={19} />}
                {data.bilan_equilibre ? "Bilan équilibré" : "À vérifier"}
              </div>
              <div className="text-sm font-semibold">Écart : {money(data.ecart)}</div>
            </div>
            {data.resultat_deja_comptabilise && (
              <p className="mt-2 text-sm">
                Le résultat CPC de {money(data.resultat_cpc)} est déjà identifié dans un compte explicitement configuré ou une clôture comptabilisée ; il n'est pas ajouté une seconde fois.
              </p>
            )}
            {!data.resultat_deja_comptabilise && Number(data.resultat_non_affecte) !== 0 && <p className="mt-2 text-sm">Résultat non affecté présenté séparément : {money(data.resultat_non_affecte)}. Aucune ligne fictive n'a été créée.</p>}
          </section>
        )}

        {data?.statut === "a_verifier" && data.anomalies.length > 0 && (
          <section className="mb-5 rounded-xl border border-amber-200 bg-white p-4 text-sm text-amber-900 shadow-sm">
            <div className="mb-2 flex items-center gap-2 font-bold">
              <TriangleAlert size={18} /> Points à vérifier
            </div>
            <ul className="list-disc space-y-1 pl-5">
              {data.anomalies.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </section>
        )}

        <section className="mb-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
            <div className="border-b bg-emerald-50 px-4 py-3 font-bold text-emerald-950">ACTIF</div>
            {data?.actif.map((item) => <SummaryRow key={item.code} label={item.libelle} value={item.montant} subtract={item.montant.startsWith("-")} />)}
            <SummaryRow label="TOTAL ACTIF" value={data?.total_actif ?? "0"} strong />
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
            <div className="border-b bg-sky-50 px-4 py-3 font-bold text-sky-950">PASSIF</div>
            {data?.passif.map((item) => <SummaryRow key={item.code} label={item.libelle} value={item.montant} />)}
            <SummaryRow label="TOTAL PASSIF" value={data?.total_passif ?? "0"} strong />
          </div>
        </section>

        <section className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
            <div>
              <h2 className="font-bold text-gray-900">Détail par compte</h2>
              <p className="text-xs text-gray-500">
                {data?.nombre_comptes ?? 0} compte(s) de bilan · {data?.nombre_lignes ?? 0} ligne(s) validée(s) analysée(s)
              </p>
            </div>
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-600">
              Clôture {data?.date_cloture ?? `${annee}-12-31`}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Côté</th>
                  <th className="px-4 py-3">Rubrique</th>
                  <th className="px-4 py-3">Compte</th>
                  <th className="px-4 py-3">Libellé</th>
                  <th className="px-4 py-3 text-right">Débit</th>
                  <th className="px-4 py-3 text-right">Crédit</th>
                  <th className="px-4 py-3 text-right">Montant bilan</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">Chargement…</td></tr>
                )}
                {!loading && grouped.flatMap(([key, items]) => items.map((item) => (
                  <tr key={`${key}-${item.compte}`} className="border-t border-gray-100">
                    <td className="px-4 py-3 font-semibold capitalize">{item.cote.replace("_", " ")}</td>
                    <td className="px-4 py-3">{RUBRIQUE_LABELS[item.rubrique] ?? item.rubrique}</td>
                    <td className="px-4 py-3 font-semibold">{item.compte}</td>
                    <td className="px-4 py-3">{item.libelle_compte ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{money(item.debit)}</td>
                    <td className="px-4 py-3 text-right">{money(item.credit)}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${item.est_compte_correcteur ? "text-amber-700" : ""}`}>
                      {money(item.montant_bilan)}
                    </td>
                  </tr>
                ))) }
                {!loading && (!data || data.comptes.length === 0) && (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">Aucun compte de bilan validé pour cet exercice.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
