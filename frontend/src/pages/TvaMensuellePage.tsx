import { useState, useEffect, useCallback } from "react";
import { listEntreprises } from "../api/entreprisesApi";
import { getTvaMensuelle } from "../api/accountingApi";
import type { Entreprise } from "../types/entreprise";
import type { TvaAnnuelle } from "../types/registre";

const MOIS_LABELS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const ANNEES = [2026, 2025, 2024, 2023];

function formatMontant(valeur: string): string {
  return `${parseFloat(valeur).toFixed(2)} MAD`;
}

export function TvaMensuellePage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState<string>("");
  const [annee, setAnnee] = useState<number>(ANNEES[0]);
  const [donnees, setDonnees] = useState<TvaAnnuelle | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    listEntreprises().then((data) => {
      setEntreprises(data);
      if (data.length > 0) setEntrepriseId(data[0].id);
    });
  }, []);

  const refresh = useCallback(async () => {
    if (!entrepriseId) return;
    setIsLoading(true);
    try {
      const data = await getTvaMensuelle({ entreprise_id: entrepriseId, annee });
      setDonnees(data);
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, annee]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const maxValeur = donnees
    ? Math.max(
        ...donnees.mensualites.map((m) =>
          Math.max(Math.abs(parseFloat(m.tva_collectee)), Math.abs(parseFloat(m.tva_deductible)))
        ),
        1
      )
    : 1;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-xl font-semibold mb-1">TVA — Vue mensuelle</h1>
        <p className="text-sm text-gray-500 mb-6">
          Calculée à partir des écritures validées uniquement.
        </p>

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

        {donnees && !isLoading && (
          <>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow-sm p-4">
                <p className="text-xs text-gray-400 uppercase">TVA collectée (année)</p>
                <p className="text-xl font-semibold text-blue-600">
                  {formatMontant(donnees.total_tva_collectee)}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow-sm p-4">
                <p className="text-xs text-gray-400 uppercase">TVA déductible (année)</p>
                <p className="text-xl font-semibold text-purple-600">
                  {formatMontant(donnees.total_tva_deductible)}
                </p>
              </div>
              <div className="bg-white rounded-lg shadow-sm p-4">
                <p className="text-xs text-gray-400 uppercase">TVA nette (année)</p>
                <p className={`text-xl font-semibold ${parseFloat(donnees.total_tva_nette) >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {formatMontant(donnees.total_tva_nette)}
                </p>
              </div>
            </div>

            {/* Graphique en barres, collectée vs déductible, par mois */}
            <div className="bg-white rounded-lg shadow-sm p-5 mb-6">
              <h2 className="text-sm font-medium mb-4">Répartition mensuelle</h2>
              <div className="flex items-end gap-2 h-48">
                {donnees.mensualites.map((m) => {
                  const collectee = parseFloat(m.tva_collectee);
                  const deductible = parseFloat(m.tva_deductible);
                  return (
                    <div key={m.mois} className="flex-1 flex flex-col items-center gap-1">
                      <div className="w-full flex items-end justify-center gap-0.5 h-40">
                        <div
                          className="w-1/2 bg-blue-500 rounded-t"
                          style={{ height: `${(collectee / maxValeur) * 100}%` }}
                          title={`Collectée : ${collectee.toFixed(2)} MAD`}
                        />
                        <div
                          className="w-1/2 bg-purple-400 rounded-t"
                          style={{ height: `${(deductible / maxValeur) * 100}%` }}
                          title={`Déductible : ${deductible.toFixed(2)} MAD`}
                        />
                      </div>
                      <span className="text-[10px] text-gray-400">{MOIS_LABELS[m.mois - 1].slice(0, 3)}</span>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-4 mt-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 bg-blue-500 rounded-sm inline-block" /> Collectée
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 bg-purple-400 rounded-sm inline-block" /> Déductible
                </span>
              </div>
            </div>

            {/* Tableau détaillé */}
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b bg-gray-50">
                    <th className="p-3">Mois</th>
                    <th className="p-3 text-right">TVA collectée</th>
                    <th className="p-3 text-right">TVA déductible</th>
                    <th className="p-3 text-right">TVA nette</th>
                    <th className="p-3 text-right">Écritures</th>
                  </tr>
                </thead>
                <tbody>
                  {donnees.mensualites.map((m) => (
                    <tr key={m.mois} className="border-b last:border-0">
                      <td className="p-3">{MOIS_LABELS[m.mois - 1]}</td>
                      <td className="p-3 text-right">{formatMontant(m.tva_collectee)}</td>
                      <td className="p-3 text-right">{formatMontant(m.tva_deductible)}</td>
                      <td className={`p-3 text-right font-medium ${parseFloat(m.tva_nette) >= 0 ? "text-green-700" : "text-red-600"}`}>
                        {formatMontant(m.tva_nette)}
                      </td>
                      <td className="p-3 text-right text-gray-400">{m.nombre_ecritures}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}