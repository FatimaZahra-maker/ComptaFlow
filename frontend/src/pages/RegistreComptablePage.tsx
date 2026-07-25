import { useState, useEffect, useCallback } from "react";
import { listEntreprises } from "../api/entreprisesApi";
import { getRegistre } from "../api/accountingApi";
import type { Entreprise } from "../types/entreprise";
import type { Registre } from "../types/registre";
import { AnomalyBadge } from "../components/AnomalyBadge";

const CATEGORIES = [
  "achats", "ventes", "banque", "cnss", "tva", "impots", "clients", "fournisseurs", "divers",
];

const MOIS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const ANNEES = [2026, 2025, 2024];

const API_BASE_URL = "http://localhost:8000";

// NOUVEAU : Fonction utilitaire pour sécuriser le parsing des montants potentiellement nuls
function formatMontant(valeur: string | null | undefined): string {
  if (valeur === null || valeur === undefined || valeur === "") return "—";
  const parsed = parseFloat(valeur);
  if (isNaN(parsed)) return "—";
  return parsed.toFixed(2);
}

export function RegistreComptablePage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState<string>("");
  const [categorie, setCategorie] = useState<string>(CATEGORIES[0]);
  const [annee, setAnnee] = useState<number>(ANNEES[0]);
  const [mois, setMois] = useState<number>(new Date().getMonth() + 1);

  const [registre, setRegistre] = useState<Registre | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEntreprises().then((data) => {
      setEntreprises(data);
      if (data.length > 0) setEntrepriseId(data[0].id);
    });
  }, []);

  const refresh = useCallback(async () => {
    if (!entrepriseId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getRegistre({ entreprise_id: entrepriseId, categorie, annee, mois });
      setRegistre(data);
    } catch {
      setError("Impossible de calculer ce registre.");
      setRegistre(null);
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, categorie, annee, mois]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function urlExport(format: "xlsx" | "csv" | "pdf") {
    const token = localStorage.getItem("comptaflow_token");
    const params = new URLSearchParams({
      entreprise_id: entrepriseId,
      categorie,
      annee: String(annee),
      mois: String(mois),
    });
    return `${API_BASE_URL}/export/registers/${format}?${params.toString()}&token=${token}`;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-xl font-semibold mb-1">Registre comptable</h1>
            <p className="text-sm text-gray-500">
              Totaux calculés à partir des écritures validées (rien n'est stocké ici).
            </p>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-4 mb-6 flex flex-wrap gap-3">
          <select
            value={entrepriseId}
            onChange={(e) => setEntrepriseId(e.target.value)}
            className="border rounded px-3 py-2 text-sm"
          >
            {entreprises.map((e) => (
              <option key={e.id} value={e.id}>{e.nom}</option>
            ))}
          </select>

          <select
            value={categorie}
            onChange={(e) => setCategorie(e.target.value)}
            className="border rounded px-3 py-2 text-sm capitalize"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c} className="capitalize">{c}</option>
            ))}
          </select>

          <select
            value={mois}
            onChange={(e) => setMois(Number(e.target.value))}
            className="border rounded px-3 py-2 text-sm"
          >
            {MOIS.map((nom, index) => (
              <option key={nom} value={index + 1}>{nom}</option>
            ))}
          </select>

          <select
            value={annee}
            onChange={(e) => setAnnee(Number(e.target.value))}
            className="border rounded px-3 py-2 text-sm"
          >
            {ANNEES.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        {isLoading && <p className="text-sm text-gray-500 mb-4">Calcul en cours...</p>}
        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        {registre && !isLoading && (
          <>
            <div className="flex justify-between items-end mb-6">
              <div className="grid grid-cols-4 gap-4 flex-1">
                <div className="bg-white rounded-lg shadow-sm p-4">
                  <p className="text-xs text-gray-400 uppercase">Écritures</p>
                  <p className="text-lg font-semibold">{registre.nombre}</p>
                </div>
                <div className="bg-white rounded-lg shadow-sm p-4">
                  <p className="text-xs text-gray-400 uppercase">Total HT</p>
                  <p className="text-lg font-semibold">{formatMontant(registre.total_ht)} MAD</p>
                </div>
                <div className="bg-white rounded-lg shadow-sm p-4">
                  <p className="text-xs text-gray-400 uppercase">Total TVA</p>
                  <p className="text-lg font-semibold">{formatMontant(registre.total_tva)} MAD</p>
                </div>
                <div className="bg-white rounded-lg shadow-sm p-4">
                  <p className="text-xs text-gray-400 uppercase">Total TTC</p>
                  <p className="text-lg font-semibold">{formatMontant(registre.total_ttc)} MAD</p>
                </div>
              </div>
            </div>

            <div className="flex gap-2 mb-4">
              <a
                href={urlExport("xlsx")}
                className="text-sm px-3 py-1.5 rounded border bg-white hover:bg-gray-50"
              >
                📊 Excel
              </a>
              <a
                href={urlExport("csv")}
                className="text-sm px-3 py-1.5 rounded border bg-white hover:bg-gray-50"
              >
                📄 CSV
              </a>
              <a
                href={urlExport("pdf")}
                className="text-sm px-3 py-1.5 rounded border bg-white hover:bg-gray-50"
              >
                🖨 PDF
              </a>
            </div>

            <div className="bg-white rounded-lg shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="p-3">Date</th>
                    <th className="p-3">Tiers</th>
                    <th className="p-3">N° pièce</th>
                    <th className="p-3">HT</th>
                    <th className="p-3">TVA</th>
                    <th className="p-3">TTC</th>
                  </tr>
                </thead>
                <tbody>
                  {registre.lignes.map((ligne) => (
                    <tr key={ligne.id} className="border-b last:border-0">
                      <td className="p-3">
                        {ligne.date_piece ? new Date(ligne.date_piece).toLocaleDateString("fr-FR") : "—"}
                      </td>
                      <td className="p-3">
                        {ligne.tiers ?? "—"}{" "}
                        <AnomalyBadge detected={ligne.anomalie_detectee} details={ligne.anomalie_details} />
                      </td>
                      <td className="p-3">{ligne.numero_piece ?? "—"}</td>
                      {/* Utilisation de la nouvelle fonction pour éviter l'erreur TypeScript */}
                      <td className="p-3">{formatMontant(ligne.montant_ht)}</td>
                      <td className="p-3">{formatMontant(ligne.montant_tva)}</td>
                      <td className="p-3">{formatMontant(ligne.montant_ttc)}</td>
                    </tr>
                  ))}
                  {registre.lignes.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-gray-400">
                        Aucune écriture validée pour ces filtres.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}