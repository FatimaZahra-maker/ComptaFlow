import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle2, ClipboardCheck, RefreshCw, TriangleAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPreClotureControls } from "../api/controlsApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { PreClotureControls, ControlLevel } from "../types/controls";
import type { Entreprise } from "../types/entreprise";

const MODULE_LABELS: Record<string, string> = {
  documents: "Documents", ecritures: "Écritures", banque: "Banque",
  devises: "Devises", tva: "TVA", cloture: "Clôture",
  grand_livre_balance: "Grand Livre / Balance", cpc: "CPC", bilan: "Bilan",
};
const LEVEL_CLASSES: Record<ControlLevel, string> = {
  bloquant: "border-red-200 bg-red-50 text-red-800",
  important: "border-amber-200 bg-amber-50 text-amber-900",
  avertissement: "border-blue-200 bg-blue-50 text-blue-900",
  information: "border-slate-200 bg-slate-50 text-slate-700",
};

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible.";
    return `Erreur API ${error.response.status}.`;
  }
  return "Erreur inattendue.";
}

export function PreCloturePage() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<PreClotureControls | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    listAvailableEntreprises("controls", year).then((items) => {
      setCompanies(items);
      const active = localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
      setCompanyId((current) => chooseAvailableEntreprise(items, current, active));
    }).catch((reason) => setError(errorMessage(reason)));
  }, [year]);

  const load = useCallback(async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await getPreClotureControls(companyId, year));
    } catch (reason) {
      setData(null);
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [companyId, year]);

  useEffect(() => { void load(); }, [load]);

  return <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
    <div className="mx-auto max-w-[1400px]">
      <header className="mb-6">
        <div className="flex items-center gap-2 text-green-700"><ClipboardCheck size={22} /><span className="text-sm font-semibold">Contrôles comptables</span></div>
        <h1 className="mt-1 text-3xl font-bold text-gray-950">Pré-clôture</h1>
        <p className="mt-1 text-sm text-gray-500">Lecture dynamique des données existantes, sans écriture ni correction automatique.</p>
      </header>

      <section className="mb-5 grid gap-3 rounded-xl border bg-white p-4 shadow-sm md:grid-cols-[1fr_180px_auto]">
        <label className="text-sm font-medium text-gray-700">Entreprise
          <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
            <option value="">Sélectionner</option>
            {companies.map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-gray-700">Exercice
          <input type="number" min={2000} max={2100} value={year} onChange={(event) => setYear(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
        </label>
        <button type="button" onClick={() => void load()} className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-gray-950 px-4 text-sm font-semibold text-white"><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Actualiser</button>
      </section>

      {companies.length === 0 && <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise ne possède encore de données dans ce module.</div>}

      {error && <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {data && <>
        <section className={`mb-5 flex flex-wrap items-center gap-5 rounded-xl border p-5 ${data.statut === "bloque" ? "border-red-200 bg-red-50" : data.statut === "a_verifier" ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}>
          {data.statut === "pret" ? <CheckCircle2 className="text-emerald-700" size={36} /> : <TriangleAlert className={data.statut === "bloque" ? "text-red-700" : "text-amber-700"} size={36} />}
          <div><p className="text-3xl font-bold">{data.score}/100</p><p className="font-semibold">{data.statut === "pret" ? "Prêt techniquement" : data.statut === "bloque" ? "Clôture bloquée" : "À vérifier"}</p></div>
          <p className="max-w-2xl text-xs text-gray-600">{data.avertissement_score}</p>
        </section>

        <section className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.values(data.resume).map((item) => <div key={item.module} className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between"><p className="font-bold">{MODULE_LABELS[item.module] ?? item.module}</p><span className={`rounded-full px-2 py-1 text-xs font-bold ${item.statut === "bloque" ? "bg-red-100 text-red-700" : item.statut === "a_verifier" ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{item.statut === "ok" ? "OK" : item.statut === "bloque" ? "Bloqué" : "À vérifier"}</span></div>
            <p className="mt-2 text-sm text-gray-500">{item.total_anomalies} anomalie(s) · {item.bloquants} bloquante(s)</p>
          </div>)}
        </section>

        <section className="overflow-hidden rounded-xl border bg-white shadow-sm">
          <div className="border-b px-5 py-4"><h2 className="font-bold">Anomalies prioritaires</h2><p className="text-xs text-gray-500">Triées par niveau puis par module. Ouvrez la source pour instruire chaque point.</p></div>
          <div className="divide-y">
            {data.anomalies.map((item, index) => <button key={`${item.code}-${item.objet_id ?? index}`} type="button" disabled={!item.route_frontend} onClick={() => item.route_frontend && navigate(item.route_frontend)} className="flex w-full items-start gap-4 px-5 py-4 text-left hover:bg-gray-50 disabled:cursor-default">
              <span className={`rounded-md border px-2 py-1 text-[11px] font-bold uppercase ${LEVEL_CLASSES[item.niveau]}`}>{item.niveau}</span>
              <span className="min-w-0 flex-1"><span className="block font-semibold text-gray-900">{item.titre}</span><span className="mt-1 block text-sm text-gray-600">{item.description}</span><span className="mt-1 block text-xs text-gray-400">{MODULE_LABELS[item.module] ?? item.module} · {item.code}</span></span>
            </button>)}
            {!loading && data.anomalies.length === 0 && <div className="px-5 py-10 text-center text-sm text-emerald-700"><CheckCircle2 className="mx-auto mb-2" />Aucune anomalie technique connue pour cet exercice.</div>}
          </div>
        </section>
      </>}
    </div>
  </div>;
}
