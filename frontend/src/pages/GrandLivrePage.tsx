import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { BookOpen, ExternalLink, RefreshCw, Search } from "lucide-react";

import { openDocumentFile } from "../api/documentsApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import { getGrandLivre, rebuildLedger } from "../api/ledgerApi";
import { ACTIVE_ENTREPRISE_KEY } from "../components/Layout";
import type { Entreprise } from "../types/entreprise";
import type { GrandLivre } from "../types/ledger";

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

function topazeLabel(value: string | null): string {
  if (value === "saisie_topaze") return "Saisie dans Topaze";
  if (value === "prete_topaze" || value === "valide") return "Prête pour Topaze";
  return "—";
}

export function GrandLivrePage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");
  const [comptePrefix, setComptePrefix] = useState("");
  const [journal, setJournal] = useState("");
  const [statutTopaze, setStatutTopaze] = useState("");
  const [tiers, setTiers] = useState("");
  const [recherche, setRecherche] = useState("");
  const [data, setData] = useState<GrandLivre | null>(null);
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAvailableEntreprises("ledger").then((items) => {
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
      const result = await getGrandLivre({
        entreprise_id: entrepriseId,
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
        compte_prefix: comptePrefix.trim() || undefined,
        journal: journal || undefined,
        statut_topaze: statutTopaze || undefined,
        tiers: tiers.trim() || undefined,
        recherche: recherche.trim() || undefined,
      });
      setData(result);
    } catch (err) {
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, dateDebut, dateFin, comptePrefix, journal, statutTopaze, tiers, recherche]);

  useEffect(() => {
    void load();
  }, [load]);

  const rebuild = async () => {
    if (!entrepriseId) return;
    setRebuilding(true);
    setError(null);
    try {
      await rebuildLedger(entrepriseId);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRebuilding(false);
    }
  };

  const selectedName = useMemo(
    () => entreprises.find((item) => item.id === entrepriseId)?.nom ?? "Entreprise",
    [entreprises, entrepriseId],
  );

  return (
    <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-emerald-700">
              <BookOpen size={22} />
              <span className="text-sm font-semibold">Comptabilité générale</span>
            </div>
            <h1 className="mt-1 text-3xl font-bold text-gray-950">Grand Livre</h1>
            <p className="mt-1 text-sm text-gray-500">
              Pré-écritures contrôlées, regroupées par compte et exprimées en MAD.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void rebuild()}
            disabled={!entrepriseId || rebuilding}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={16} className={rebuilding ? "animate-spin" : ""} />
            Reconstruire les lignes
          </button>
        </div>

        <section className="mb-5 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm md:grid-cols-4">
          <label className="text-sm font-medium text-gray-700">
            Entreprise
            <select
              value={entrepriseId}
              onChange={(e) => setEntrepriseId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            >
              <option value="">Sélectionner</option>
              {entreprises.map((item) => (
                <option key={item.id} value={item.id}>{item.nom}</option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">
            Du
            <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-gray-700">
            Au
            <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="text-sm font-medium text-gray-700">
            Compte / famille
            <div className="relative mt-1">
              <Search size={15} className="absolute left-3 top-3 text-gray-400" />
              <input
                value={comptePrefix}
                onChange={(e) => setComptePrefix(e.target.value)}
                placeholder="ex. 44, 6121, 5141"
                className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3"
              />
            </div>
          </label>
          <label className="text-sm font-medium text-gray-700">Journal<select value={journal} onChange={(e) => setJournal(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"><option value="">Tous</option><option value="ACH">Achats</option><option value="VTE">Ventes</option><option value="BQ">Banque</option><option value="OD">Opérations diverses</option></select></label>
          <label className="text-sm font-medium text-gray-700">Statut Topaze<select value={statutTopaze} onChange={(e) => setStatutTopaze(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"><option value="">Tous</option><option value="prete_topaze">Prête pour Topaze</option><option value="saisie_topaze">Saisie dans Topaze</option></select></label>
          <label className="text-sm font-medium text-gray-700">Fournisseur / client<input value={tiers} onChange={(e) => setTiers(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="Nom du tiers" /></label>
          <label className="text-sm font-medium text-gray-700">Pièce ou libellé<input value={recherche} onChange={(e) => setRecherche(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" placeholder="Recherche" /></label>
          </section>
        {entreprises.length === 0 && <p className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Aucune entreprise ne possède encore de données dans ce module.</p>}

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Entreprise</p><p className="mt-1 font-bold">{selectedName}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Comptes</p><p className="mt-1 text-2xl font-bold">{data?.nombre_comptes ?? 0}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Total débit</p><p className="mt-1 font-bold">{money(data?.total_debit)}</p></div>
          <div className="rounded-xl bg-white p-4 shadow-sm"><p className="text-xs uppercase text-gray-400">Total crédit</p><p className="mt-1 font-bold">{money(data?.total_credit)}</p><p className={`text-xs ${data?.equilibre ? "text-emerald-600" : "text-red-600"}`}>{data?.equilibre ? "Équilibré" : "Non équilibré"}</p></div>
        </section>

        {loading ? (
          <div className="rounded-xl bg-white p-12 text-center text-gray-500"><RefreshCw className="mr-2 inline animate-spin" size={18} />Chargement…</div>
        ) : data?.comptes.length ? (
          <div className="space-y-4">
            {data.comptes.map((compte) => (
              <section key={compte.compte} className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-gray-50 px-5 py-3">
                  <div><p className="font-bold text-gray-950">{compte.compte} — {compte.libelle_compte ?? "Compte non libellé"}</p><p className="text-xs text-gray-500">Solde initial {money(compte.solde_initial)} • Solde final {money(compte.solde_final)}</p></div>
                  <div className="text-right text-xs text-gray-500">Débit {money(compte.total_debit)}<br />Crédit {money(compte.total_credit)}</div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1250px] text-sm">
                    <thead className="bg-white text-left text-xs uppercase text-gray-400"><tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Jnal</th><th className="px-4 py-3">Pièce</th><th className="px-4 py-3">Tiers</th><th className="px-4 py-3">Libellé</th><th className="px-4 py-3">Statut Topaze</th><th className="px-4 py-3">Source</th><th className="px-4 py-3 text-right">Débit</th><th className="px-4 py-3 text-right">Crédit</th><th className="px-4 py-3 text-right">Solde</th></tr></thead>
                    <tbody>{compte.lignes.map((ligne) => <tr key={ligne.id} className="border-t border-gray-100"><td className="px-4 py-3">{new Date(`${ligne.date_ecriture}T00:00:00`).toLocaleDateString("fr-FR")}</td><td className="px-4 py-3 font-semibold">{ligne.journal}</td><td className="px-4 py-3">{ligne.numero_piece ?? "—"}</td><td className="px-4 py-3">{ligne.tiers ?? "—"}</td><td className="px-4 py-3">{ligne.libelle}</td><td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${ligne.statut_topaze === "saisie_topaze" ? "bg-indigo-100 text-indigo-800" : "bg-emerald-100 text-emerald-800"}`}>{topazeLabel(ligne.statut_topaze)}</span></td><td className="px-4 py-3">{ligne.document_id ? <button type="button" onClick={() => void openDocumentFile(ligne.document_id!)} className="inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline"><ExternalLink size={14} /> Document</button> : "—"}</td><td className="px-4 py-3 text-right">{Number(ligne.debit) ? money(ligne.debit) : "—"}</td><td className="px-4 py-3 text-right">{Number(ligne.credit) ? money(ligne.credit) : "—"}</td><td className="px-4 py-3 text-right font-semibold">{money(ligne.solde_cumule)}</td></tr>)}</tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-gray-100 bg-white p-12 text-center text-gray-400">Aucune ligne validée. Validez des écritures ou utilisez « Reconstruire les lignes ».</div>
        )}
      </div>
    </div>
  );
}
