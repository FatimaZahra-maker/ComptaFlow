import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Building2, Search } from "lucide-react";
import { listEntreprises } from "../api/entreprisesApi";
import { setActiveEntrepriseId } from "../utils/activeEntreprise";
import type { Entreprise } from "../types/entreprise";

export function CompanySelectionPage() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEntreprises().then((items) => setCompanies(items.filter((item) => item.is_active !== false && !item.creee_automatiquement))).catch(() => setError("Impossible de charger les entreprises autorisées.")).finally(() => setLoading(false));
  }, []);

  const results = useMemo(() => {
    const term = query.trim().toLocaleLowerCase("fr");
    if (!term) return companies.slice(0, 12);
    return companies.filter((company) => [company.nom, company.ice, company.identifiant_fiscal, company.rc].some((value) => value?.toLocaleLowerCase("fr").includes(term))).slice(0, 20);
  }, [companies, query]);

  function selectCompany(company: Entreprise) {
    setActiveEntrepriseId(company.id);
    navigate(`/dashboard?entreprise_id=${company.id}`);
  }

  return <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 p-5 sm:p-9">
    <div className="mx-auto max-w-5xl">
      <button type="button" onClick={() => navigate("/accueil")} className="mb-7 inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold text-slate-600 hover:bg-white"><ArrowLeft size={17}/> Retour à l’accueil</button>
      <div className="rounded-3xl border border-white bg-white/90 p-6 shadow-xl shadow-blue-950/10 sm:p-10">
        <div className="mx-auto max-w-2xl text-center"><span className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-blue-950 text-white shadow-lg"><Building2 size={31}/></span><h1 className="mt-5 text-3xl font-black text-blue-950">Travailler sur une entreprise</h1><p className="mt-2 text-slate-500">Recherchez rapidement un dossier par nom, ICE, IF ou RC.</p></div>
        <div className="relative mx-auto mt-8 max-w-2xl"><Search className="absolute left-4 top-1/2 -translate-y-1/2 text-blue-600"/><input autoFocus type="search" value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Ex. ANZO, ICE, IF ou RC…" className="w-full rounded-2xl border border-slate-200 bg-slate-50 py-4 pl-12 pr-4 text-lg outline-none transition focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-500/10"/></div>
        {error && <p className="mx-auto mt-5 max-w-2xl rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</p>}
        <div className="mx-auto mt-6 grid max-w-3xl gap-3">
          {loading && <p className="py-10 text-center text-slate-400">Chargement des dossiers…</p>}
          {!loading && results.map((company)=><button type="button" key={company.id} onClick={()=>selectCompany(company)} className="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-500/20"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-blue-50 font-black text-blue-700">{company.nom.slice(0,2).toUpperCase()}</span><span className="min-w-0 flex-1"><strong className="block truncate text-lg text-slate-900">{company.nom}</strong><small className="mt-1 block text-slate-500">{[company.ice&&`ICE : ${company.ice}`,company.identifiant_fiscal&&`IF : ${company.identifiant_fiscal}`,company.rc&&`RC : ${company.rc}`].filter(Boolean).join(" · ")||"Aucun identifiant renseigné"}</small></span><ArrowRight className="text-blue-600 transition group-hover:translate-x-1"/></button>)}
          {!loading && companies.length===0 && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center"><Building2 className="mx-auto text-slate-300" size={42}/><h2 className="mt-3 font-bold text-slate-700">Aucune entreprise enregistrée</h2><p className="mt-1 text-sm text-slate-500">Vous pouvez commencer par importer des documents ; ComptaFlow tentera d’identifier leur entreprise.</p><button type="button" onClick={()=>navigate("/upload")} className="mt-5 rounded-xl bg-blue-700 px-5 py-3 font-bold text-white">Importer des documents</button></div>}
          {!loading && companies.length>0 && results.length===0 && <p className="rounded-2xl border border-dashed border-slate-300 py-10 text-center text-slate-500">Aucune entreprise autorisée ne correspond à « {query} ».</p>}
        </div>
        <button type="button" onClick={()=>navigate("/chronos?non_identifies=1")} className="mx-auto mt-8 block text-sm font-bold text-amber-700 hover:underline">Consulter les documents dont l’entreprise reste à identifier</button>
      </div>
    </div>
  </div>;
}
