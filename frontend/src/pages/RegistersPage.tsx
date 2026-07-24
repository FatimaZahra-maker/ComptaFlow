import { useState, useEffect, useCallback } from "react";
import { listEntries, validateEntry, rejectEntry } from "../api/accountingApi";
import type { Ecriture } from "../types/ecriture";
import { AnomalyBadge } from "../components/AnomalyBadge";

const STATUT_LABELS: Record<string, string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validé",
  rejete: "Rejeté",
};

export function RegistersPage() {
  const [entries, setEntries] = useState<Ecriture[]>([]);
  const [filtre, setFiltre] = useState<string>("");
  const [processingId, setProcessingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const data = await listEntries(filtre || undefined);
    setEntries(data);
  }, [filtre]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleValidate(id: string) {
    setProcessingId(id);
    try {
      await validateEntry(id);
      await refresh();
    } finally {
      setProcessingId(null);
    }
  }

  async function handleReject(id: string) {
    setProcessingId(id);
    try {
      await rejectEntry(id);
      await refresh();
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-xl font-semibold mb-4">Registres comptables</h1>

        <select
          value={filtre}
          onChange={(e) => setFiltre(e.target.value)}
          className="mb-4 border rounded px-3 py-2 text-sm"
        >
          <option value="">Tous les statuts</option>
          <option value="brouillon">Brouillon</option>
          <option value="a_verifier">À vérifier</option>
          <option value="valide">Validé</option>
          <option value="rejete">Rejeté</option>
        </select>

        <div className="bg-white rounded-lg shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="p-3">Tiers</th>
                <th className="p-3">Montant TTC</th>
                <th className="p-3">Statut</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className={`border-b last:border-0 ${entry.anomalie_detectee ? "bg-orange-50" : ""}`}>
                  <td className="p-3">{entry.tiers ?? "—"}</td>
                  <td className="p-3">{parseFloat(entry.montant_ttc).toFixed(2)} MAD</td>
                  <td className="p-3">
                    <span className="mr-2">{STATUT_LABELS[entry.statut_validation]}</span>
                    <AnomalyBadge detected={entry.anomalie_detectee} details={entry.anomalie_details} />
                  </td>
                  <td className="p-3 space-x-2">
                    <button
                      onClick={() => handleValidate(entry.id)}
                      disabled={processingId === entry.id || entry.statut_validation === "valide"}
                      className="text-green-600 text-xs font-medium disabled:opacity-40"
                    >
                      Valider
                    </button>
                    <button
                      onClick={() => handleReject(entry.id)}
                      disabled={processingId === entry.id || entry.statut_validation === "rejete"}
                      className="text-red-600 text-xs font-medium disabled:opacity-40"
                    >
                      Rejeter
                    </button>
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-6 text-center text-gray-400">
                    Aucune écriture pour l'instant.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}