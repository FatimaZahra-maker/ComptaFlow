import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  CheckCircle2,
  Download,
  ExternalLink,
  FileSearch,
  RefreshCw,
  Search,
  XCircle,
} from "lucide-react";

import {
  listEntries,
  rejectEntry,
  toggleSaisieTopaze,
  validateEntry,
} from "../api/accountingApi";
import { openDocumentFile } from "../api/documentsApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { AnomalyBadge } from "./AnomalyBadge";
import {
  exportRowsToCsv,
  exportRowsToExcel,
  type ExportColumn,
} from "../utils/tableExport";

import type {
  Ecriture,
  PeriodiciteComptable,
  StatutValidation,
  TypeEcriture,
} from "../types/ecriture";
import type { Entreprise } from "../types/entreprise";

const STATUS_LABELS: Record<string, string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validée",
  rejete: "Rejetée",
};

const STATUS_CLASSES: Record<string, string> = {
  brouillon: "bg-slate-100 text-slate-700",
  a_verifier: "bg-orange-100 text-orange-700",
  valide: "bg-green-100 text-green-700",
  rejete: "bg-red-100 text-red-700",
};

const MONTHS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const PAGE_SIZE = 15;

function amount(value: string | null): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value: string | number | null): string {
  const parsed = typeof value === "number" ? value : amount(value);
  return `${new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed)} MAD`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("fr-FR");
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible. Vérifiez Uvicorn.";
  }
  return "Une erreur est survenue. Réessayez.";
}

interface EntriesTablePageProps {
  title: string;
  description: string;
  typeEcriture?: TypeEcriture;
  emptyMessage?: string;
}

export function EntriesTablePage({
  title,
  description,
  typeEcriture,
  emptyMessage = "Aucune écriture ne correspond aux filtres.",
}: EntriesTablePageProps) {
  const navigate = useNavigate();
  const [now] = useState(() => new Date());

  const [entries, setEntries] = useState<Ecriture[]>([]);
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [status, setStatus] = useState<StatutValidation | "">("");
  const [searchTerm, setSearchTerm] = useState("");
  const [year, setYear] = useState<number | "">("");
  const [periodicity, setPeriodicity] = useState<PeriodiciteComptable>("annuelle");
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [quarter, setQuarter] = useState(Math.floor(now.getMonth() / 3) + 1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const years = useMemo(
    () => Array.from({ length: 7 }, (_, index) => now.getFullYear() + 1 - index),
    [now],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listEntries({
        entreprise_id: companyId || undefined,
        statut_validation: status || undefined,
        type_ecriture: typeEcriture,
        recherche: searchTerm.trim() || undefined,
        annee: year === "" ? undefined : year,
        periodicite: year === "" ? undefined : periodicity,
        mois: year !== "" && periodicity === "mensuelle" ? month : undefined,
        trimestre: year !== "" && periodicity === "trimestrielle" ? quarter : undefined,
      });
      setEntries(data);
      setPage(1);
    } catch (requestError) {
      setEntries([]);
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [companyId, month, periodicity, quarter, searchTerm, status, typeEcriture, year]);

  useEffect(() => {
    const module = typeEcriture === "achat" ? "achats" : typeEcriture === "vente" ? "ventes" : "ecritures";
    listAvailableEntreprises(module)
      .then((items) => {
        setCompanies(items);
        setCompanyId((current) => chooseAvailableEntreprise(items, current));
      })
      .catch(() => setError("Impossible de charger les entreprises."));
  }, [typeEcriture]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void refresh(), 250);
    return () => window.clearTimeout(timeout);
  }, [refresh]);

  const totals = useMemo(
    () => entries.reduce(
      (accumulator, entry) => ({
        ht: accumulator.ht + amount(entry.montant_ht),
        tva: accumulator.tva + amount(entry.montant_tva),
        ttc: accumulator.ttc + amount(entry.montant_ttc),
      }),
      { ht: 0, tva: 0, ttc: 0 },
    ),
    [entries],
  );

  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const visibleEntries = entries.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const periodLabel = year === ""
    ? "Toutes les années"
    : periodicity === "mensuelle"
      ? `${MONTHS[month - 1]} ${year}`
      : periodicity === "trimestrielle"
        ? `T${quarter} ${year}`
        : `Année ${year}`;

  const exportColumns: ExportColumn<Ecriture>[] = [
    { header: "Date", value: (entry) => formatDate(entry.date_piece) },
    { header: "Entreprise", value: (entry) => entry.entreprise_nom ?? "" },
    { header: typeEcriture === "vente" ? "Client" : typeEcriture === "achat" ? "Fournisseur" : "Tiers", value: (entry) => entry.tiers ?? "" },
    { header: typeEcriture === "vente" ? "Compte client" : typeEcriture === "achat" ? "Compte fournisseur" : "Compte tiers", value: (entry) => entry.compte_tiers ?? "" },
    { header: "Compte TVA", value: (entry) => entry.compte_tva ?? "" },
    { header: typeEcriture === "vente" ? "Compte produit" : "Compte HT", value: (entry) => entry.compte_ht ?? "" },
    { header: "Libellé", value: (entry) => entry.libelle ?? "" },
    { header: "N° pièce", value: (entry) => entry.numero_piece ?? "" },
    { header: "Catégorie", value: (entry) => entry.categorie_document ?? entry.type_ecriture },
    { header: "HT", value: (entry) => amount(entry.montant_ht) },
    { header: "TVA", value: (entry) => amount(entry.montant_tva) },
    { header: "TTC", value: (entry) => amount(entry.montant_ttc) },
    { header: "Validation", value: (entry) => STATUS_LABELS[entry.statut_validation] },
    { header: "Saisie Topaze", value: (entry) => entry.saisie_topaze ? "Oui" : "Non" },
    { header: "Fichier", value: (entry) => entry.nom_fichier_document ?? "" },
  ];

  async function runAction(
    key: string,
    action: () => Promise<Ecriture>,
    message: string,
  ): Promise<void> {
    setCurrentAction(key);
    setError(null);
    setSuccess(null);
    try {
      await action();
      await refresh();
      setSuccess(message);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setCurrentAction(null);
    }
  }

  const safeTitle = title.toLowerCase().replace(/[^a-z0-9]+/g, "_");

  return (
    <div className="min-h-full bg-slate-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1700px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
            <p className="mt-1 text-sm text-slate-500">{description}</p>
            <p className="mt-1 text-xs font-semibold text-green-700">Période : {periodLabel}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => exportRowsToCsv(`${safeTitle}_${year || "toutes_annees"}.csv`, entries, exportColumns)}
              disabled={entries.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-40"
            ><Download size={16} /> CSV</button>
            <button
              type="button"
              onClick={() => exportRowsToExcel(`${safeTitle}_${year || "toutes_annees"}.xls`, title, entries, exportColumns)}
              disabled={entries.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-40"
            ><Download size={16} /> Excel</button>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50"
            ><RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Actualiser</button>
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <section className="mb-5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1.3fr_220px_180px_130px_180px_180px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
              <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Tiers, pièce ou fichier..." className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-green-500 focus:ring-4 focus:ring-green-500/10" />
            </div>
            <select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm"><option value="">Toutes les entreprises</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.nom}</option>)}</select>
            <select value={status} onChange={(event) => setStatus(event.target.value as StatutValidation | "")} className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm"><option value="">Tous les statuts</option><option value="brouillon">Brouillon</option><option value="a_verifier">À vérifier</option><option value="valide">Validée</option><option value="rejete">Rejetée</option></select>
            <select
              value={year}
              onChange={(event) => setYear(event.target.value ? Number(event.target.value) : "")}
              className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
            >
              <option value="">Toutes les années</option>
              {years.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select
              value={periodicity}
              onChange={(event) => setPeriodicity(event.target.value as PeriodiciteComptable)}
              disabled={year === ""}
              className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm disabled:bg-slate-100 disabled:text-slate-400"
            >
              <option value="mensuelle">Mensuelle</option>
              <option value="trimestrielle">Trimestrielle</option>
              <option value="annuelle">Annuelle</option>
            </select>
            {year === "" ? (
              <div className="flex items-center rounded-lg border border-green-200 bg-green-50 px-3 text-sm font-semibold text-green-700">Toutes les périodes</div>
            ) : periodicity === "mensuelle" ? (
              <select value={month} onChange={(event) => setMonth(Number(event.target.value))} className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm">{MONTHS.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}</select>
            ) : periodicity === "trimestrielle" ? (
              <select value={quarter} onChange={(event) => setQuarter(Number(event.target.value))} className="rounded-lg border border-slate-300 px-3 py-2.5 text-sm"><option value={1}>1er trimestre</option><option value={2}>2e trimestre</option><option value={3}>3e trimestre</option><option value={4}>4e trimestre</option></select>
            ) : <div className="flex items-center rounded-lg border border-green-200 bg-green-50 px-3 text-sm font-semibold text-green-700">Toute l’année</div>}
          </div>
          {companies.length === 0 && !loading && <p className="mt-3 text-sm text-amber-700">Aucune entreprise ne possÃ¨de encore de donnÃ©es dans ce module.</p>}
        </section>

        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[["Écritures", String(entries.length)], ["Total HT", formatMoney(totals.ht)], ["Total TVA", formatMoney(totals.tva)], ["Total TTC", formatMoney(totals.ttc)]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-2 text-xl font-bold text-slate-900">{value}</p></div>)}
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1900px] text-sm">
              <thead className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Entreprise</th><th className="px-4 py-3">{typeEcriture === "vente" ? "Client" : typeEcriture === "achat" ? "Fournisseur" : "Tiers"}</th><th className="px-4 py-3">{typeEcriture === "vente" ? "Compte client" : typeEcriture === "achat" ? "Compte fournisseur" : "Compte tiers"}</th><th className="px-4 py-3">Compte TVA</th><th className="px-4 py-3">{typeEcriture === "vente" ? "Compte produit" : "Compte HT"}</th><th className="px-4 py-3">Libellé</th><th className="px-4 py-3">N° pièce</th><th className="px-4 py-3">Catégorie</th><th className="px-4 py-3 text-right">HT</th><th className="px-4 py-3 text-right">TVA</th><th className="px-4 py-3 text-right">TTC</th><th className="px-4 py-3">Validation</th><th className="px-4 py-3 text-center">Saisie</th><th className="px-4 py-3">Actions</th></tr></thead>
              <tbody>
                {loading && <tr><td colSpan={15} className="px-4 py-10 text-center text-slate-400">Chargement...</td></tr>}
                {!loading && visibleEntries.map((entry) => <tr key={entry.id} className="border-b last:border-0 hover:bg-slate-50/70"><td className="px-4 py-3">{formatDate(entry.date_piece)}</td><td className="px-4 py-3 font-medium">{entry.entreprise_nom ?? "—"}</td><td className="px-4 py-3">{entry.tiers ?? "—"}</td><td className="px-4 py-3 font-mono text-xs">{entry.compte_tiers ?? "—"}</td><td className="px-4 py-3 font-mono text-xs">{entry.compte_tva ?? "—"}</td><td className="px-4 py-3 font-mono text-xs">{entry.compte_ht ?? "—"}</td><td className="max-w-[260px] truncate px-4 py-3" title={entry.libelle ?? undefined}>{entry.libelle ?? "—"}</td><td className="px-4 py-3">{entry.numero_piece ?? "—"}</td><td className="px-4 py-3 capitalize">{entry.categorie_document ?? entry.type_ecriture}</td><td className="px-4 py-3 text-right">{formatMoney(entry.montant_ht)}</td><td className="px-4 py-3 text-right">{formatMoney(entry.montant_tva)}</td><td className="px-4 py-3 text-right font-bold">{formatMoney(entry.montant_ttc)}</td><td className="px-4 py-3"><div className="flex items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_CLASSES[entry.statut_validation]}`}>{STATUS_LABELS[entry.statut_validation]}</span><AnomalyBadge detected={entry.anomalie_detectee} details={entry.anomalie_details} /></div></td><td className="px-4 py-3 text-center"><input type="checkbox" checked={entry.saisie_topaze} disabled={currentAction === `saisie-${entry.id}`} onChange={() => void runAction(`saisie-${entry.id}`, () => toggleSaisieTopaze(entry.id), "Statut de saisie mis à jour.")} className="h-4 w-4 accent-green-600" /></td><td className="px-4 py-3"><div className="flex gap-1 whitespace-nowrap"><button type="button" onClick={() => navigate(`/documents/${entry.document_id}`)} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"><FileSearch size={14} /> Vérifier</button><button type="button" onClick={() => void openDocumentFile(entry.document_id)} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"><ExternalLink size={14} /> Fichier</button>{entry.statut_validation !== "valide" && <button type="button" onClick={() => void runAction(`valider-${entry.id}`, () => validateEntry(entry.id), "Écriture validée.")} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"><CheckCircle2 size={14} /> Valider</button>}{entry.statut_validation !== "rejete" && <button type="button" onClick={() => void runAction(`rejeter-${entry.id}`, () => rejectEntry(entry.id), "Écriture rejetée.")} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"><XCircle size={14} /> Rejeter</button>}</div></td></tr>)}
                {!loading && entries.length === 0 && <tr><td colSpan={15} className="px-4 py-12 text-center text-slate-400">{emptyMessage}</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-slate-500"><span>{entries.length} écriture(s)</span><div className="flex items-center gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))} className="rounded border px-3 py-1.5 disabled:opacity-40">Précédent</button><span>Page {page} / {totalPages}</span><button type="button" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))} className="rounded border px-3 py-1.5 disabled:opacity-40">Suivant</button></div></div>
        </div>
      </div>
    </div>
  );
}
