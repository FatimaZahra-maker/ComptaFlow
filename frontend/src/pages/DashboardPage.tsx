import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getDashboard } from "../api/dashboardApi";
import type { Dashboard } from "../types/dashboard";

// Libellés lisibles pour chaque statut de document, utilisés pour
// afficher le bloc "Documents" du tableau de bord (§ Phase 6).
const DOCUMENT_STATUT_LABELS: Record<keyof Dashboard["documents_par_statut"], string> = {
  en_attente: "En attente",
  en_traitement: "En traitement",
  traite: "Traités",
  valide: "Validés",
  erreur: "Erreur",
};

const DOCUMENT_STATUT_COLORS: Record<keyof Dashboard["documents_par_statut"], string> = {
  en_attente: "text-gray-600",
  en_traitement: "text-yellow-600",
  traite: "text-blue-600",
  valide: "text-green-600",
  erreur: "text-red-600",
};

const ECRITURE_STATUT_LABELS: Record<keyof Dashboard["ecritures_par_statut"], string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validées",
  rejete: "Rejetées",
};

const ECRITURE_STATUT_COLORS: Record<keyof Dashboard["ecritures_par_statut"], string> = {
  brouillon: "text-gray-600",
  a_verifier: "text-orange-600",
  valide: "text-green-600",
  rejete: "text-red-600",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    getDashboard()
      .then(setDashboard)
      .catch(() => setError("Impossible de charger le tableau de bord."))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return <div className="p-8 text-gray-500">Chargement...</div>;
  }

  if (error || !dashboard) {
    return <div className="p-8 text-red-600">{error ?? "Erreur inconnue."}</div>;
  }

  const tvaNetteNum = parseFloat(dashboard.tva_nette);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-xl font-semibold mb-6">Tableau de bord</h1>

        {/* --- Bloc Documents --- */}
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase mb-2">Documents ({dashboard.total_documents})</p>
          <div className="grid grid-cols-5 gap-4">
            {(Object.keys(dashboard.documents_par_statut) as Array<keyof Dashboard["documents_par_statut"]>).map(
              (statut) => (
                <button
                  key={statut}
                  onClick={() => navigate("/chronos")}
                  className="bg-white rounded-lg shadow-sm p-4 text-left hover:shadow-md transition"
                >
                  <p className="text-xs text-gray-400">{DOCUMENT_STATUT_LABELS[statut]}</p>
                  <p className={`text-2xl font-semibold ${DOCUMENT_STATUT_COLORS[statut]}`}>
                    {dashboard.documents_par_statut[statut]}
                  </p>
                </button>
              )
            )}
          </div>
        </div>

        {/* --- Bloc TVA --- */}
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase mb-2">TVA</p>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-xs text-gray-400">TVA collectée</p>
              <p className="text-2xl font-semibold text-blue-600">
                {parseFloat(dashboard.tva_collectee).toFixed(2)} MAD
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-xs text-gray-400">TVA déductible</p>
              <p className="text-2xl font-semibold text-purple-600">
                {parseFloat(dashboard.tva_deductible).toFixed(2)} MAD
              </p>
            </div>
            <div className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-xs text-gray-400">TVA nette</p>
              <p className={`text-2xl font-semibold ${tvaNetteNum >= 0 ? "text-green-600" : "text-red-600"}`}>
                {tvaNetteNum.toFixed(2)} MAD
              </p>
            </div>
          </div>
        </div>

        {/* --- Bloc Écritures --- */}
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase mb-2">Écritures ({dashboard.total_ecritures})</p>
          <div className="grid grid-cols-4 gap-4">
            {(Object.keys(dashboard.ecritures_par_statut) as Array<keyof Dashboard["ecritures_par_statut"]>).map(
              (statut) => (
                <button
                  key={statut}
                  onClick={() => navigate("/registers")}
                  className="bg-white rounded-lg shadow-sm p-4 text-left hover:shadow-md transition"
                >
                  <p className="text-xs text-gray-400">{ECRITURE_STATUT_LABELS[statut]}</p>
                  <p className={`text-2xl font-semibold ${ECRITURE_STATUT_COLORS[statut]}`}>
                    {dashboard.ecritures_par_statut[statut]}
                  </p>
                </button>
              )
            )}
          </div>
        </div>

        {/* --- Bloc Entreprises --- */}
        <div>
          <p className="text-xs text-gray-400 uppercase mb-2">Cabinet</p>
          <div className="bg-white rounded-lg shadow-sm p-4 w-fit">
            <p className="text-xs text-gray-400">Entreprises</p>
            <p className="text-2xl font-semibold">{dashboard.total_entreprises}</p>
          </div>
        </div>
      </div>
    </div>
  );
}