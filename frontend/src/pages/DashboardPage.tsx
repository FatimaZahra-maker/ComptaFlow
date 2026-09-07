import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { getDashboard } from "../api/dashboardApi";
import type { Dashboard } from "../types/dashboard";
import { ACTIVE_ENTREPRISE_EVENT, getActiveEntrepriseId, setActiveEntrepriseId } from "../utils/activeEntreprise";

// --- ICÔNES SVG NATIVES ---
const IconWrapper = ({ children, className }: { children: React.ReactNode, className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    {children}
  </svg>
);

const Icons = {
  Clock: ({ className }: any) => <IconWrapper className={className}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></IconWrapper>,
  RefreshCw: ({ className }: any) => <IconWrapper className={className}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></IconWrapper>,
  CheckCircle2: ({ className }: any) => <IconWrapper className={className}><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></IconWrapper>,
  XCircle: ({ className }: any) => <IconWrapper className={className}><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></IconWrapper>,
  FileText: ({ className }: any) => <IconWrapper className={className}><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></IconWrapper>,
  AlertTriangle: ({ className }: any) => <IconWrapper className={className}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></IconWrapper>,
  AlertCircle: ({ className }: any) => <IconWrapper className={className}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></IconWrapper>,
  ArrowRight: ({ className }: any) => <IconWrapper className={className}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></IconWrapper>,
  Building2: ({ className }: any) => <IconWrapper className={className}><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></IconWrapper>,
  Calendar: ({ className }: any) => <IconWrapper className={className}><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></IconWrapper>
};

function dashboardErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (!error.response) return "Backend inaccessible. Vérifiez que le serveur est démarré.";
    return `Le tableau de bord est indisponible (erreur ${error.response.status}).`;
  }
  return "Impossible de charger le tableau de bord.";
}

const StatCard = ({ title, value, icon: Icon, colorText, colorBg, onClick }: { title: string, value: number | string, icon: any, colorText: string, colorBg: string, onClick: () => void }) => (
  <button 
    onClick={onClick}
    className="flex w-full flex-col justify-between rounded-[10px] border border-slate-200 bg-white p-4 text-left shadow-[0_1px_3px_rgba(15,23,42,0.05)] transition-all hover:border-blue-200 hover:shadow-md"
  >
    <div className="mb-2 flex w-full items-start justify-between">
      <h3 className="text-sm font-semibold text-slate-600">{title}</h3>
      <div className={`p-2 rounded-lg ${colorBg}`}>
        <Icon className={`w-5 h-5 ${colorText}`} />
      </div>
    </div>
    <div className="flex items-baseline gap-2">
      <span className={`text-2xl font-bold ${colorText === 'text-slate-600' ? 'text-slate-900' : colorText}`}>
        {value}
      </span>
    </div>
  </button>
);

export function DashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // La vue globale évite d'afficher un tableau vide simplement parce que le
  // mois courant ne contient encore aucun document.
  const [period, setPeriod] = useState("");
  const [entrepriseId, setEntrepriseId] = useState<string | null>(() => getActiveEntrepriseId());

  useEffect(() => {
    const synchronize = (event: Event) => setEntrepriseId((event as CustomEvent<string | null>).detail ?? null);
    window.addEventListener(ACTIVE_ENTREPRISE_EVENT, synchronize);
    return () => window.removeEventListener(ACTIVE_ENTREPRISE_EVENT, synchronize);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setError(null); // CORRECTION 1 : Réinitialiser l'erreur
    
    getDashboard(period || undefined, entrepriseId)
      .then(setDashboard)
      .catch((requestError: unknown) => setError(dashboardErrorMessage(requestError)))
      .finally(() => setIsLoading(false));
  }, [entrepriseId, period]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="animate-spin text-blue-600">
          <Icons.RefreshCw className="w-8 h-8" />
        </div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl flex items-center gap-3">
          <Icons.AlertCircle className="w-6 h-6" />
          <p className="font-medium">{error ?? "Aucune donnée disponible."}</p>
        </div>
      </div>
    );
  }

  // CORRECTION 2 : Utilisation de Number() pour éviter les erreurs TypeScript
  const tvaCollecteeNum = Number(dashboard.tva_collectee) || 0;
  const tvaDeductibleNum = Number(dashboard.tva_deductible) || 0;
  const tvaNetteNum = Number(dashboard.tva_nette) || 0;
  
  const docErrors = dashboard.documents_par_statut?.erreur || 0;
  const ecrituresVerification = dashboard.ecritures_par_statut?.a_verifier || 0;
  const hasUrgencies = docErrors > 0 || ecrituresVerification > 0;

  return (
    <div className="mx-auto w-full max-w-[1500px] p-5 sm:p-6 lg:p-8">
      
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600">Pilotage financier</p><h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-950">Vue d'ensemble</h1><p className="mt-1 text-sm text-slate-500">Résumé opérationnel des documents et écritures du dossier.</p><div className="mt-2 flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${entrepriseId ? "bg-blue-100 text-blue-700" : "bg-slate-200 text-slate-700"}`}>Périmètre : {entrepriseId ? "entreprise sélectionnée" : "tout le cabinet"}</span>{entrepriseId && <button type="button" onClick={() => setActiveEntrepriseId(null)} className="text-xs font-semibold text-blue-700 hover:underline">Afficher toutes les entreprises</button>}</div></div>
        
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setPeriod("")}
            className={`rounded-xl border px-4 py-2 text-sm font-semibold shadow-sm transition-colors ${!period ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
          >
            Toutes les périodes
          </button>
          <div className="flex items-center gap-3 bg-white border border-slate-200 px-4 py-2 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-500 transition-all">
            <Icons.Calendar className="w-5 h-5 text-blue-600" />
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              aria-label="Filtrer le tableau de bord par mois"
              className="bg-transparent border-none focus:outline-none text-sm font-semibold text-slate-700 cursor-pointer w-full"
            />
          </div>
        </div>
      </div>

      {hasUrgencies && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-10 flex flex-col sm:flex-row sm:items-center justify-between shadow-sm gap-4">
          <div className="flex items-center gap-4">
            <div className="bg-amber-100 p-3 rounded-full shrink-0">
              <Icons.AlertCircle className="w-6 h-6 text-amber-600" />
            </div>
            <div>
              <h2 className="text-amber-900 font-bold text-lg">Actions requises</h2>
              <p className="text-amber-700 text-sm mt-1">
                {docErrors > 0 && <><strong className="font-semibold text-red-600">{docErrors} documents</strong> sont en erreur. </>}
                {ecrituresVerification > 0 && <><strong className="font-semibold text-amber-600">{ecrituresVerification} écritures</strong> nécessitent une vérification.</>}
              </p>
            </div>
          </div>
          <button 
            onClick={() => navigate(docErrors > 0 ? "/chronos" : "/registers")}
            className="flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
          >
            Résoudre
            <Icons.ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      <section className="mb-6">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Indicateurs principaux</h2>
          <span className="text-sm font-medium text-slate-500">Données de la période sélectionnée</span>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard title="Documents" value={dashboard.total_documents || 0} icon={Icons.FileText} colorText="text-blue-600" colorBg="bg-blue-50" onClick={() => navigate("/chronos")} />
          <StatCard title="Écritures" value={dashboard.total_ecritures || 0} icon={Icons.FileText} colorText="text-blue-600" colorBg="bg-blue-50" onClick={() => navigate("/registers")} />
          <StatCard title="Topaze à saisir" value={(dashboard.ecritures_par_statut?.prete_topaze || 0) + (dashboard.ecritures_par_statut?.valide || 0)} icon={Icons.CheckCircle2} colorText="text-emerald-600" colorBg="bg-green-50" onClick={() => navigate("/registers")} />
          <StatCard title="Anomalies à traiter" value={docErrors + ecrituresVerification} icon={Icons.AlertTriangle} colorText={(docErrors + ecrituresVerification) > 0 ? "text-amber-600" : "text-emerald-600"} colorBg={(docErrors + ecrituresVerification) > 0 ? "bg-amber-50" : "bg-green-50"} onClick={() => navigate(docErrors > 0 ? "/chronos" : "/registers")} />
        </div>
      </section>

      <section className="mb-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_rgba(15,23,42,0.05)]">
        <div className="border-b border-slate-200 px-5 py-4"><h2 className="text-lg font-bold text-slate-950">Processus de traitement documentaire</h2><p className="text-xs text-slate-500">Lecture directe des volumes disponibles dans les statuts actuels.</p></div>
        <div className="grid divide-y divide-slate-200 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-6">
          {[
            ["Documents reçus", dashboard.total_documents || 0],
            ["En analyse", dashboard.documents_par_statut?.en_traitement || 0],
            ["Données extraites", dashboard.documents_par_statut?.traite || 0],
            ["Contrôlés", dashboard.documents_par_statut?.valide || 0],
            ["Écritures proposées", dashboard.total_ecritures || 0],
            ["Validées / saisies", (dashboard.ecritures_par_statut?.prete_topaze || 0) + (dashboard.ecritures_par_statut?.valide || 0) + (dashboard.ecritures_par_statut?.saisie_topaze || 0)],
          ].map(([label, value]) => <div key={String(label)} className="relative px-4 py-4"><p className="text-2xl font-bold text-slate-950">{value}</p><p className="mt-1 text-xs font-medium text-slate-500">{label}</p></div>)}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="lg:col-span-6">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Écritures Comptables</h2>
            <span className="text-sm font-medium text-slate-500">Total : {dashboard.total_ecritures || 0}</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <StatCard title="Brouillon" value={dashboard.ecritures_par_statut?.brouillon || 0} icon={Icons.FileText} colorText="text-slate-600" colorBg="bg-slate-100" onClick={() => navigate("/registers")} />
            <StatCard title="Calcul en cours" value={dashboard.ecritures_par_statut?.calcul_en_cours || 0} icon={Icons.RefreshCw} colorText="text-blue-600" colorBg="bg-blue-50" onClick={() => navigate("/registers")} />
            <StatCard title="À vérifier" value={ecrituresVerification} icon={Icons.AlertTriangle} colorText="text-amber-600" colorBg="bg-amber-50" onClick={() => navigate("/registers")} />
            <StatCard title="Prêtes pour Topaze" value={(dashboard.ecritures_par_statut?.prete_topaze || 0) + (dashboard.ecritures_par_statut?.valide || 0)} icon={Icons.CheckCircle2} colorText="text-emerald-600" colorBg="bg-emerald-50" onClick={() => navigate("/registers")} />
            <StatCard title="Saisies dans Topaze" value={dashboard.ecritures_par_statut?.saisie_topaze || 0} icon={Icons.CheckCircle2} colorText="text-indigo-600" colorBg="bg-indigo-50" onClick={() => navigate("/registers")} />
            <StatCard title="Rejetées" value={dashboard.ecritures_par_statut?.rejete || 0} icon={Icons.XCircle} colorText="text-red-600" colorBg="bg-red-50" onClick={() => navigate("/registers")} />
          </div>
        </section>

        <section className="lg:col-span-4">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Situation TVA (Période)</h2>
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm h-[calc(100%-2rem)] flex flex-col justify-center">
            <div className="space-y-6">
              <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                <span className="text-sm font-medium text-slate-600">TVA Collectée</span>
                <span className="text-lg font-bold text-blue-600">{tvaCollecteeNum.toFixed(2)} MAD</span>
              </div>
              <div className="flex justify-between items-center pb-4 border-b border-slate-100">
                <span className="text-sm font-medium text-slate-600">TVA Déductible</span>
                <span className="text-lg font-bold text-purple-600">{tvaDeductibleNum.toFixed(2)} MAD</span>
              </div>
              <div className="flex justify-between items-center pt-2">
                <span className="text-sm font-bold text-slate-800">TVA Nette</span>
                <span className={`text-xl font-black ${tvaNetteNum >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                  {tvaNetteNum.toFixed(2)} MAD
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="lg:col-span-2">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Cabinet</h2>
          <div className="bg-slate-800 rounded-xl p-6 shadow-sm text-white h-[calc(100%-2rem)] flex flex-col justify-center items-center text-center">
            <div className="bg-slate-700/50 p-3 rounded-full mb-3">
              <Icons.Building2 className="w-6 h-6 text-slate-300" />
            </div>
            <p className="text-sm text-slate-400 font-medium mb-1">Entreprises</p>
            <p className="text-3xl font-bold text-white">{dashboard.total_entreprises || 0}</p>
          </div>
        </section>
      </div>
    </div>
  );
}
