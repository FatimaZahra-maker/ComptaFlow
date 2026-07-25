import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { listEntreprises } from "../api/entreprisesApi";
import { listChronoDocuments, listAnneesDisponibles } from "../api/chronosApi";
import { getDocumentFileUrl, retraiterDocument } from "../api/documentsApi";
import { toggleSaisieTopaze } from "../api/accountingApi";
import { ResizableSidebar } from "../components/ResizableSidebar";
import type { Entreprise } from "../types/entreprise";
import type { DocumentChrono } from "../types/chrono";
import { AnomalyBadge } from "../components/AnomalyBadge";

const CATEGORIES = [
  "achats", "ventes", "banque", "cnss", "tva", "impots", "clients", "fournisseurs", "divers",
];

const MOIS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const STATUT_DOC_COLORS: Record<string, string> = {
  en_attente: "text-gray-500",
  en_traitement: "text-yellow-600",
  traite: "text-green-600",
  erreur: "text-red-600",
};

const STATUT_VALIDATION_LABELS: Record<string, string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validé",
  rejete: "Rejeté",
};

const STATUT_VALIDATION_COLORS: Record<string, string> = {
  brouillon: "bg-gray-100 text-gray-600",
  a_verifier: "bg-orange-100 text-orange-700",
  valide: "bg-green-100 text-green-700",
  rejete: "bg-red-100 text-red-700",
};

const CATEGORIE_COLORS: Record<string, string> = {
  achats: "bg-blue-50 text-blue-700",
  fournisseurs: "bg-blue-50 text-blue-700",
  ventes: "bg-emerald-50 text-emerald-700",
  clients: "bg-emerald-50 text-emerald-700",
  banque: "bg-purple-50 text-purple-700",
  cnss: "bg-pink-50 text-pink-700",
  tva: "bg-amber-50 text-amber-700",
  impots: "bg-amber-50 text-amber-700",
  divers: "bg-gray-100 text-gray-600",
};

function formatMontant(valeur: string | number | null | undefined): string {
  if (valeur === null || valeur === undefined || valeur === "") return "—";
  const parsed = typeof valeur === 'string' ? parseFloat(valeur) : valeur;
  if (isNaN(parsed)) return "—";
  return `${parsed.toFixed(2)} MAD`;
}

export function ChronosPage() {
  const navigate = useNavigate();
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [documents, setDocuments] = useState<DocumentChrono[]>([]);
  const [anneesDisponibles, setAnneesDisponibles] = useState<number[]>([]);
  const [entrepriseId, setEntrepriseId] = useState<string | null>(null);
  const [categorie, setCategorie] = useState<string | null>(null);
  const [annee, setAnnee] = useState<number | null>(null);
  const [mois, setMois] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [retraitementEnCours, setRetraitementEnCours] = useState<string | null>(null);

  useEffect(() => {
    listEntreprises().then(setEntreprises);
  }, []);

  useEffect(() => {
    listAnneesDisponibles({
      entreprise_id: entrepriseId ?? undefined,
      categorie: categorie ?? undefined,
    }).then((annees) => {
      setAnneesDisponibles(annees);
      if (annee !== null && !annees.includes(annee)) {
        setAnnee(null);
      }
    });
  }, [entrepriseId, categorie]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listChronoDocuments({
        entreprise_id: entrepriseId ?? undefined,
        categorie: categorie ?? undefined,
        annee: annee ?? undefined,
        mois: mois ?? undefined,
      });
      setDocuments(data);
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, categorie, annee, mois]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function handleConsulter(e: React.MouseEvent, documentId: string) {
    e.stopPropagation();
    window.open(getDocumentFileUrl(documentId), "_blank");
  }

  async function handleToggleSaisie(e: React.MouseEvent, ecritureId: string) {
    e.stopPropagation();
    await toggleSaisieTopaze(ecritureId);
    await refresh();
  }

  async function handleRetraiter(e: React.MouseEvent, documentId: string) {
    e.stopPropagation();
    setRetraitementEnCours(documentId);
    try {
      await retraiterDocument(documentId);
      await refresh();
    } catch {
      // Ignore
    } finally {
      setRetraitementEnCours(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <ResizableSidebar storageKey="chronos-filters" defaultWidth={224} minWidth={180} maxWidth={400} className="border-r bg-white">
        <div className="p-4 space-y-6">
          <div>
            <p className="text-xs text-gray-400 uppercase mb-2">Entreprises</p>
            <button
              onClick={() => setEntrepriseId(null)}
              className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                entrepriseId === null ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
              }`}
            >
              Toutes
            </button>
            {entreprises.map((e) => (
              <button
                key={e.id}
                onClick={() => setEntrepriseId(e.id)}
                className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                  entrepriseId === e.id ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
                }`}
              >
                {e.nom}
                {e.creee_automatiquement && (
                  <span className="ml-1 text-orange-400 text-xs" title="Créée automatiquement, à vérifier">●</span>
                )}
              </button>
            ))}
          </div>

          <div>
            <p className="text-xs text-gray-400 uppercase mb-2">Catégories</p>
            <button
              onClick={() => setCategorie(null)}
              className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                categorie === null ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
              }`}
            >
              Toutes
            </button>
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCategorie(c)}
                className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 capitalize ${
                  categorie === c ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
                }`}
              >
                {c}
              </button>
            ))}
          </div>

          <div>
            <p className="text-xs text-gray-400 uppercase mb-2">Année</p>
            <button
              onClick={() => setAnnee(null)}
              className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                annee === null ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
              }`}
            >
              Toutes
            </button>
            {anneesDisponibles.length === 0 && (
              <p className="text-xs text-gray-300 px-2 py-1">Aucune donnée</p>
            )}
            {anneesDisponibles.map((a) => (
              <button
                key={a}
                onClick={() => setAnnee(a)}
                className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                  annee === a ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
                }`}
              >
                {a}
              </button>
            ))}
          </div>

          <div>
            <p className="text-xs text-gray-400 uppercase mb-2">Mois</p>
            <button
              onClick={() => setMois(null)}
              className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                mois === null ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
              }`}
            >
              Tous
            </button>
            {MOIS.map((nom, index) => (
              <button
                key={nom}
                onClick={() => setMois(index + 1)}
                className={`block w-full text-left px-2 py-1.5 rounded text-sm mb-0.5 ${
                  mois === index + 1 ? "bg-green-100 text-green-700" : "hover:bg-gray-50"
                }`}
              >
                {nom}
              </button>
            ))}
          </div>
        </div>
      </ResizableSidebar>

      <div className="flex-1 min-w-0 p-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-semibold">Chronos — Tableau comptable</h1>
          <p className="text-sm text-gray-400">{documents.length} document(s)</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm overflow-x-auto">
          <table className="w-full min-w-[1400px] text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b bg-gray-50">
                <th className="p-3">Fichier</th>
                <th className="p-3">Entreprise</th>
                <th className="p-3">Catégorie</th>
                <th className="p-3">N° facture</th>
                <th className="p-3">Date</th>
                <th className="p-3">Tiers</th>
                <th className="p-3 text-right">HT</th>
                <th className="p-3 text-right">TVA</th>
                <th className="p-3 text-right">TTC</th>
                <th className="p-3">Statut doc.</th>
                <th className="p-3">Validation</th>
                <th className="p-3">Saisie</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={13} className="p-6 text-center text-gray-400">Chargement...</td></tr>
              )}

              {!isLoading && documents.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  className="border-b last:border-0 hover:bg-gray-50 cursor-pointer"
                >
                  <td className="p-3 max-w-[140px] truncate" title={doc.nom_fichier_original}>
                    {doc.nom_fichier_original}
                  </td>
                  <td className="p-3">{doc.entreprise_nom ?? "—"}</td>
                  <td className="p-3">
                    {doc.categorie ? (
                      <span className={`px-2 py-0.5 rounded text-xs capitalize ${CATEGORIE_COLORS[doc.categorie] ?? "bg-gray-100 text-gray-600"}`}>
                        {doc.categorie}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="p-3">{doc.numero_piece ?? "—"}</td>
                  <td className="p-3">
                    {doc.date_piece ? new Date(doc.date_piece).toLocaleDateString("fr-FR") : "—"}
                  </td>
                  <td className="p-3">{doc.tiers ?? "—"}</td>
                  <td className="p-3 text-right">{formatMontant(doc.montant_ht)}</td>
                  <td className="p-3 text-right">
                    {formatMontant(doc.montant_tva)}
                    {doc.taux_tva && <span className="text-gray-400 text-xs ml-1">({doc.taux_tva}%)</span>}
                  </td>
                  <td className="p-3 text-right font-medium">{formatMontant(doc.montant_ttc)}</td>
                  <td className={`p-3 font-medium ${STATUT_DOC_COLORS[doc.statut] ?? ""}`}>{doc.statut}</td>
                  <td className="p-3">
                    {doc.statut_validation ? (
                      <span className="flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-xs ${STATUT_VALIDATION_COLORS[doc.statut_validation]}`}>
                          {STATUT_VALIDATION_LABELS[doc.statut_validation]}
                        </span>
                        <AnomalyBadge detected={doc.anomalie_detectee} details={doc.anomalie_details} />
                      </span>
                    ) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="p-3">
                    {doc.ecriture_id ? (
                      <input
                        type="checkbox"
                        checked={doc.saisie_topaze}
                        onChange={(e) => handleToggleSaisie(e as unknown as React.MouseEvent, doc.ecriture_id!)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 accent-green-600 cursor-pointer"
                        title="Marquer comme saisi dans Topaze"
                      />
                    ) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="p-3 whitespace-nowrap">
                    <button
                      onClick={(e) => handleConsulter(e, doc.id)}
                      className="text-xs text-blue-600 hover:text-blue-800 font-medium mr-3"
                    >
                      📄 Consulter
                    </button>
                    <button
                      onClick={(e) => handleRetraiter(e, doc.id)}
                      disabled={retraitementEnCours === doc.id}
                      className="text-xs text-green-700 hover:text-green-900 font-medium disabled:opacity-40"
                      title="Relancer le traitement OCR/IA sur ce document"
                    >
                      {retraitementEnCours === doc.id ? "⏳ ..." : "🔄 Retraiter"}
                    </button>
                  </td>
                </tr>
              ))}

              {!isLoading && documents.length === 0 && (
                <tr><td colSpan={13} className="p-6 text-center text-gray-400">Aucun document pour ces filtres.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}