import { useState, useEffect, useCallback } from "react";
import { listEntreprises } from "../api/entreprisesApi";
import { downloadRapportPdf, getRapport } from "../api/rapportsApi";
import type { Entreprise } from "../types/entreprise";
import type { Rapport } from "../types/rapport";

const ANNEES = [2026, 2025, 2024, 2023];
const MOIS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

function formatMontant(v: string): string {
  return `${parseFloat(v).toFixed(2)} MAD`;
}

// Page Rapports : sélection entreprise/période, affichage du rapport
// de synthèse calculé côté backend, et export PDF.
export function RapportsPage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [annee, setAnnee] = useState(ANNEES[0]);
  const [mois, setMois] = useState<number | null>(null); // null = année entière
  const [rapport, setRapport] = useState<Rapport | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    listEntreprises().then((data) => {
      setEntreprises(data);
      if (data.length > 0) setEntrepriseId(data[0].id);
    });
  }, []);

  // Recharge le rapport chaque fois qu'un filtre change.
  const refresh = useCallback(async () => {
    if (!entrepriseId) return;
    setIsLoading(true);
    try {
      const data = await getRapport({ entreprise_id: entrepriseId, annee, mois: mois ?? undefined });
      setRapport(data);
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, annee, mois]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-xl font-semibold mb-1">Rapports</h1>
        <p className="text-sm text-gray-500 mb-6">Synthèse calculée à partir des documents et écritures validées.</p>

        <div className="bg-white rounded-lg shadow-sm p-4 mb-6 flex flex-wrap gap-3">
          <select value={entrepriseId} onChange={(e) => setEntrepriseId(e.target.value)} className="border rounded px-3 py-2 text-sm">
            {entreprises.map((ent) => <option key={ent.id} value={ent.id}>{ent.nom}</option>)}
          </select>
          <select value={annee} onChange={(e) => setAnnee(Number(e.target.value))} className="border rounded px-3 py-2 text-sm">
            {ANNEES.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <select
            value={mois ?? ""}
            onChange={(e) => setMois(e.target.value === "" ? null : Number(e.target.value))}
            className="border rounded px-3 py-2 text-sm"
          >
            <option value="">Année entière</option>
            {MOIS.map((nom, i) => <option key={nom} value={i + 1}>{nom}</option>)}
          </select>
        </div>

        {isLoading && <p className="text-sm text-gray-500 mb-4">Calcul en cours...</p>}

        {rapport && !isLoading && (
          <>
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-medium">{rapport.entreprise_nom} — {mois ? `${MOIS[mois - 1]} ` : ""}{rapport.annee}</h2>
              
              {/* CORRECTION ICI : Ajout du "<a " devant href */}
              <button
                type="button"
                onClick={() => void downloadRapportPdf({ entreprise_id: entrepriseId, annee, mois: mois ?? undefined })}
                className="text-sm px-3 py-1.5 rounded border bg-white hover:bg-gray-50"
              >
                🖨 Exporter PDF
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-white rounded-lg shadow-sm p-4">
                <p className="text-xs text-gray-400 uppercase mb-2">Documents</p>
                <div className="flex justify-between text-sm mb-1"><span>Traités</span><span className="font-medium">{rapport.nombre_documents}</span></div>
                <div className="flex justify-between text-sm"><span>En erreur</span><span className="font-medium text-red-600">{rapport.nombre_documents_erreur}</span></div>
              </div>
              <div className="bg-white rounded-lg shadow-sm p-4">
                <p className="text-xs text-gray-400 uppercase mb-2">Écritures</p>
                <div className="flex justify-between text-sm mb-1"><span>Validées</span><span className="font-medium text-green-700">{rapport.nombre_ecritures_validees}</span></div>
                <div className="flex justify-between text-sm mb-1"><span>À vérifier</span><span className="font-medium text-orange-600">{rapport.nombre_ecritures_a_verifier}</span></div>
                <div className="flex justify-between text-sm"><span>Anomalies</span><span className="font-medium text-red-600">{rapport.nombre_anomalies}</span></div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-xs text-gray-400 uppercase mb-2">Financier (écritures validées)</p>
              <div className="grid grid-cols-2 gap-y-1.5 text-sm">
                <span>Total achats HT</span><span className="text-right font-medium">{formatMontant(rapport.total_achats_ht)}</span>
                <span>Total ventes HT</span><span className="text-right font-medium">{formatMontant(rapport.total_ventes_ht)}</span>
                <span>TVA collectée</span><span className="text-right font-medium">{formatMontant(rapport.tva_collectee)}</span>
                <span>TVA déductible</span><span className="text-right font-medium">{formatMontant(rapport.tva_deductible)}</span>
                <span className="font-medium">TVA nette</span>
                <span className={`text-right font-medium ${parseFloat(rapport.tva_nette) >= 0 ? "text-green-700" : "text-red-600"}`}>
                  {formatMontant(rapport.tva_nette)}
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
