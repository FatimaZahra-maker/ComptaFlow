import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

// --- INTERFACES ---
interface AchatRow {
  id: number;
  entreprise: string;
  annee: string;
  mois: string;
  type: string;
  fichier: string;
  tiers: string;
  cat: string;
  ref: string;
  date: string;
  libelle: string;
  ht: string;
  tva: string;
  ttc: string;
  statut: string;
  validation: string;
}

// --- MOCK DATA ---
const INITIAL_ACHATS_DATA: AchatRow[] = [
  { id: 1, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2024", mois: "Avril", type: "pdf", fichier: "fact_achat_0158.pdf", tiers: "STE ELECTROMAR SARL", cat: "Achat", ref: "FA2404-0158", date: "24/04/2024", libelle: "Achat pièces auto", ht: "5 550.00", tva: "1 110.00 (20%)", ttc: "6 660.00", statut: "Saisi", validation: "Validé" },
  { id: 2, entreprise: "TECH SOLUTIONS MAROC", annee: "2024", mois: "Juillet", type: "png", fichier: "facture_serveur.png", tiers: "BATI SERVICES SARL", cat: "Achat", ref: "FS-2024-0789", date: "24/07/2024", libelle: "Fourniture matériel", ht: "18 850.00", tva: "3 770.00 (20%)", ttc: "22 620.00", statut: "À vérifier", validation: "Nouveau" },
  { id: 3, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2024", mois: "Mai", type: "pdf", fichier: "achat_00235.pdf", tiers: "GLOBAL OFFICE SOLUTIONS", cat: "Achat", ref: "FA2405-00235", date: "23/05/2024", libelle: "Consommables bureau", ht: "24 995.00", tva: "4 999.20 (20%)", ttc: "29 993.20", statut: "Saisi", validation: "À vérifier" },
  { id: 4, entreprise: "TECH SOLUTIONS MAROC", annee: "2024", mois: "Mars", type: "pdf", fichier: "achat_mars.pdf", tiers: "STE ELECTROMAR SARL", cat: "Achat", ref: "FA2403-0312", date: "15/03/2024", libelle: "Pièces détachées", ht: "7 200.00", tva: "1 440.00 (20%)", ttc: "8 640.00", statut: "Saisi", validation: "Validé" },
];

export function AchatsPage() {
  const navigate = useNavigate();

  // --- ÉTATS ---
  const [achatsData, setAchatsData] = useState<AchatRow[]>(INITIAL_ACHATS_DATA);
  const [entreprise, setEntreprise] = useState("Toutes");
  const [annee, setAnnee] = useState("2024");
  const [mois, setMois] = useState("Tous les mois");
  
  const [editingRow, setEditingRow] = useState<AchatRow | null>(null);
  const [viewingRow, setViewingRow] = useState<AchatRow | null>(null);

  // --- LOGIQUE DE FILTRAGE ---
  const donneesFiltrees = achatsData.filter((row) => {
    const matchEntreprise = entreprise === "Toutes" || row.entreprise === entreprise;
    const matchAnnee = annee === "Toutes" || row.annee === annee;
    const matchMois = mois === "Tous les mois" || row.mois === mois;
    return matchEntreprise && matchAnnee && matchMois;
  });

  // --- ACTIONS (ÉDITION) ---
  const handleEdit = (row: AchatRow) => {
    setEditingRow({ ...row });
  };

  const handleSaveEdit = () => {
    if (editingRow) {
      setAchatsData(prev => prev.map(item => item.id === editingRow.id ? editingRow : item));
      setEditingRow(null);
    }
  };

  // --- EXPORT EXCEL (CSV) ---
  const handleExport = () => {
    if (donneesFiltrees.length === 0) return alert("Rien à exporter.");
    const headers = ["Entreprise", "Fichier", "Fournisseur", "Catégorie", "N° Facture", "Date", "Libellé", "Montant HT", "TVA", "TTC", "Statut", "Validation"];
    const rows = donneesFiltrees.map(r => [
      `"${r.entreprise}"`, `"${r.fichier}"`, `"${r.tiers}"`, `"${r.cat}"`, `"${r.ref}"`, `"${r.date}"`, `"${r.libelle}"`,
      `"${r.ht}"`, `"${r.tva.split(' ')[0]}"`, `"${r.ttc}"`, `"${r.statut}"`, `"${r.validation}"`
    ]);
    const csvContent = [headers.join(";"), ...rows.map(row => row.join(";"))].join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `Export_Achats_${entreprise.replace(/\s/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans relative">
      
      {/* --- EN-TÊTE --- */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Achats <span className="font-normal text-slate-500">— Tableau des documents d'achat</span>
        </h1>
      </div>

      {/* --- FILTRES ET ACTIONS --- */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="flex gap-4">
          <div>
            <label htmlFor="achat-entreprise" className="block text-xs font-bold text-slate-500 mb-1">Entreprise</label>
            <select 
              id="achat-entreprise"
              value={entreprise} 
              onChange={(e) => setEntreprise(e.target.value)}
              className="w-64 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes les entreprises</option>
              <option value="STE MAROC PIECES AUTO SARL">STE MAROC PIECES AUTO SARL</option>
              <option value="TECH SOLUTIONS MAROC">TECH SOLUTIONS MAROC</option>
            </select>
          </div>
          <div>
            <label htmlFor="achat-annee" className="block text-xs font-bold text-slate-500 mb-1">Année</label>
            <select 
              id="achat-annee"
              value={annee} 
              onChange={(e) => setAnnee(e.target.value)}
              className="w-32 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes</option>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
            </select>
          </div>
          <div>
            <label htmlFor="achat-mois" className="block text-xs font-bold text-slate-500 mb-1">Mois</label>
            <select 
              id="achat-mois"
              value={mois} 
              onChange={(e) => setMois(e.target.value)}
              className="w-40 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-sm"
            >
              <option value="Tous les mois">Tous les mois</option>
              <option value="Mars">Mars</option>
              <option value="Avril">Avril</option>
              <option value="Mai">Mai</option>
              <option value="Juillet">Juillet</option>
            </select>
          </div>
        </div>
        
        <div className="flex gap-3">
          <button onClick={handleExport} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-colors shadow-sm">
            Exporter vers Excel <span className="text-xs">▼</span>
          </button>
        </div>
      </div>

      {/* --- ZONE PRINCIPALE : TABLEAU + SIDEBAR --- */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        
        {/* Colonne de gauche (Tableau principal) */}
        <div className="xl:col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-xs">Entreprise ▽</th>
                  <th className="px-4 py-3 text-xs">Fichier ▽</th>
                  <th className="px-4 py-3 text-xs">Fournisseur ▽</th>
                  <th className="px-4 py-3 text-xs">N° Facture ▽</th>
                  <th className="px-4 py-3 text-xs">Date ▽</th>
                  <th className="px-4 py-3 text-xs text-right">HT ▽</th>
                  <th className="px-4 py-3 text-xs text-right">TVA ▽</th>
                  <th className="px-4 py-3 text-xs text-right">TTC ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Statut ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Validation ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {donneesFiltrees.length === 0 ? (
                   <tr>
                     <td colSpan={11} className="px-4 py-8 text-center text-slate-500 italic">
                       Aucun document trouvé pour ces filtres.
                     </td>
                   </tr>
                ) : (
                  donneesFiltrees.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700 w-32 truncate whitespace-normal leading-tight">{row.entreprise}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white shadow-sm ${row.type === 'pdf' ? 'bg-red-500' : 'bg-blue-500'}`}>
                            {row.type.toUpperCase()}
                          </span>
                          <span onClick={() => setViewingRow(row)} className="text-blue-600 font-medium text-xs hover:underline cursor-pointer">{row.fichier}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs font-bold whitespace-normal leading-tight w-32">{row.tiers}</td>
                      <td className="px-4 py-3 text-xs">{row.ref}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{row.date}</td>
                      <td className="px-4 py-3 text-xs text-right font-medium">{row.ht}</td>
                      <td className="px-4 py-3 text-xs text-right text-slate-500 flex flex-col items-end gap-0.5">
                        <span>{row.tva.split(' ')[0]}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-right font-bold text-slate-800">{row.ttc}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${row.statut === 'Saisi' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-slate-100 text-slate-600 border-slate-300'}`}>
                          {row.statut}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${row.validation === 'Validé' ? 'bg-green-50 text-green-700 border-green-200' : row.validation === 'Nouveau' ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                          {row.validation}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-3 text-slate-400 text-base">
                          <button onClick={() => setViewingRow(row)} title="Voir" className="hover:text-blue-600 transition-colors">👁</button>
                          <button onClick={() => handleEdit(row)} title="Modifier" className="hover:text-amber-500 transition-colors">✎</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Colonne de droite (Navigation) */}
        <div className="xl:col-span-1 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5">
            <h3 className="font-bold text-slate-800 mb-4 text-sm">Types de tableaux</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-2 bg-blue-50/70 border border-blue-100 rounded-lg cursor-default">
                <div className="w-9 h-9 bg-white shadow-sm border border-blue-100 text-blue-600 rounded-md flex items-center justify-center text-lg">🛒</div>
                <div>
                  <div className="text-sm font-bold text-blue-700">Achats</div>
                  <div className="text-[11px] font-medium text-blue-500">Documents d'achat</div>
                </div>
              </div>
              <div onClick={() => navigate('/ventes')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-green-50 group-hover:bg-green-100 group-hover:text-green-700 text-green-600 rounded-md flex items-center justify-center text-lg transition-colors">🛍</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-green-700 transition-colors">Ventes</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- MODALE DE MODIFICATION (STYLO) --- */}
      {editingRow && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 animate-fade-in-up">
            <div className="flex justify-between items-center mb-5 border-b border-gray-100 pb-3">
              <h2 className="text-lg font-bold text-slate-800">Modifier la facture</h2>
              <button onClick={() => setEditingRow(null)} className="text-slate-400 hover:text-red-500 text-2xl font-bold transition-colors leading-none">&times;</button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Fournisseur</label>
                  <input type="text" value={editingRow.tiers} onChange={(e) => setEditingRow({...editingRow, tiers: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">N° Facture</label>
                  <input type="text" value={editingRow.ref} onChange={(e) => setEditingRow({...editingRow, ref: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500" />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Montant HT</label>
                  <input type="text" value={editingRow.ht} onChange={(e) => setEditingRow({...editingRow, ht: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">TVA</label>
                  <input type="text" value={editingRow.tva} onChange={(e) => setEditingRow({...editingRow, tva: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Montant TTC</label>
                  <input type="text" value={editingRow.ttc} onChange={(e) => setEditingRow({...editingRow, ttc: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-100">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Statut de saisie</label>
                  <select value={editingRow.statut} onChange={(e) => setEditingRow({...editingRow, statut: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                    <option value="À vérifier">À vérifier</option>
                    <option value="Saisi">Saisi</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Validation (Chrono)</label>
                  <select value={editingRow.validation} onChange={(e) => setEditingRow({...editingRow, validation: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                    <option value="Nouveau">Nouveau</option>
                    <option value="À vérifier">À vérifier</option>
                    <option value="Validé">Validé</option>
                    <option value="Rejeté">Rejeté</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-100">
              <button onClick={() => setEditingRow(null)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-bold text-slate-600 hover:bg-slate-50">Annuler</button>
              <button onClick={handleSaveEdit} className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 shadow-sm">Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {/* --- VUE DÉTAILLÉE PLEIN ÉCRAN (ŒIL - COMME SUR image_8de49c.jpg) --- */}
      {viewingRow && (
        <div className="fixed inset-0 bg-white z-[100] flex flex-col h-screen overflow-hidden text-sm">
          
          {/* Top Bar[cite: 10] */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white shadow-sm">
            <div className="flex items-center gap-3">
              <button onClick={() => setViewingRow(null)} className="text-gray-500 hover:text-gray-800 font-bold mr-2 flex items-center gap-1">
                <span>←</span> Retour
              </button>
              <span className="text-gray-400">Documents /</span>
              <span className="font-bold text-slate-800">Facture {viewingRow.ref}</span>
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs font-semibold ml-2">Validé</span>
              <span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded text-xs font-semibold">Nouveau</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right leading-tight">
                <div className="font-bold text-slate-800">Cabinet Alpha</div>
                <div className="text-xs text-gray-500">Expert-Comptable</div>
              </div>
              <div className="w-8 h-8 bg-blue-600 rounded-full text-white flex items-center justify-center font-bold">CA</div>
            </div>
          </div>

          <div className="flex flex-1 overflow-hidden bg-gray-50">
            {/* Left side: PDF Viewer[cite: 10] */}
            <div className="w-7/12 bg-[#2D2D2D] p-6 flex flex-col relative">
              <div className="flex justify-between items-center text-white mb-4 bg-[#1E1E1E] p-2 rounded">
                <span>1 / 1</span>
                <div className="flex gap-4">
                  <button>-</button>
                  <span>100%</span>
                  <button>+</button>
                </div>
                <button>⤢</button>
              </div>
              {/* Fake PDF Paper */}
              <div className="flex-1 bg-white mx-auto w-full max-w-2xl p-10 shadow-2xl relative">
                <h1 className="text-2xl font-bold mb-8">FACTURE</h1>
                <div className="flex justify-between mb-8">
                  <div>
                    <h2 className="font-bold text-lg">{viewingRow.tiers}</h2>
                    <p className="text-gray-500 text-xs">Casablanca, Maroc</p>
                  </div>
                  <div className="text-right">
                    <p><strong>N° :</strong> {viewingRow.ref}</p>
                    <p><strong>Date :</strong> {viewingRow.date}</p>
                  </div>
                </div>
                <table className="w-full text-left mb-8 border-collapse">
                  <thead>
                    <tr className="border-b-2 border-black">
                      <th className="py-2">Désignation</th>
                      <th className="py-2 text-right">Montant HT</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-gray-200">
                      <td className="py-3">{viewingRow.libelle}</td>
                      <td className="py-3 text-right">{viewingRow.ht}</td>
                    </tr>
                  </tbody>
                </table>
                <div className="flex justify-end">
                  <div className="w-64 space-y-2">
                    <div className="flex justify-between"><span>Total HT</span><span>{viewingRow.ht}</span></div>
                    <div className="flex justify-between"><span>TVA</span><span>{viewingRow.tva.split(' ')[0]}</span></div>
                    <div className="flex justify-between font-bold text-lg border-t-2 border-black pt-2"><span>Total TTC</span><span>{viewingRow.ttc}</span></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right side: Data & Actions[cite: 10] */}
            <div className="w-5/12 bg-white border-l border-gray-200 flex flex-col">
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                
                {/* Panel 1: Extraction */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-slate-800">Informations extraites (IA)</h3>
                    <div className="text-xs text-green-600 font-bold bg-green-50 px-2 py-1 rounded">Score global : 96%</div>
                  </div>
                  <div className="grid grid-cols-2 gap-y-3 text-sm">
                    <div className="text-gray-500">Date</div><div className="text-right font-medium">{viewingRow.date}</div>
                    <div className="text-gray-500">Numéro facture</div><div className="text-right font-medium">{viewingRow.ref}</div>
                    <div className="text-gray-500">Nom fournisseur</div><div className="text-right font-medium">{viewingRow.tiers}</div>
                    <div className="text-gray-500">HT</div><div className="text-right font-medium">{viewingRow.ht} DH</div>
                    <div className="text-gray-500">TVA</div><div className="text-right font-medium">{viewingRow.tva.split(' ')[0]} DH</div>
                    <div className="text-gray-500">TTC</div><div className="text-right font-medium">{viewingRow.ttc} DH</div>
                    <div className="text-gray-500">Catégorie</div><div className="text-right font-medium">{viewingRow.cat}</div>
                  </div>
                </div>

                {/* Panel 2: Compta */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <h3 className="font-bold text-slate-800 mb-4">Écriture comptable proposée</h3>
                  <table className="w-full text-xs">
                    <thead className="text-gray-500 border-b border-gray-100">
                      <tr><th className="text-left pb-2">Compte</th><th className="text-left pb-2">Libellé</th><th className="text-right pb-2">Débit</th><th className="text-right pb-2">Crédit</th></tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      <tr><td className="py-2">6111</td><td className="py-2">Achats marchandises</td><td className="py-2 text-right">{viewingRow.ht}</td><td className="py-2 text-right">-</td></tr>
                      <tr><td className="py-2">34552</td><td className="py-2">TVA récupérable</td><td className="py-2 text-right">{viewingRow.tva.split(' ')[0]}</td><td className="py-2 text-right">-</td></tr>
                      <tr><td className="py-2">4411</td><td className="py-2">Fournisseur</td><td className="py-2 text-right">-</td><td className="py-2 text-right">{viewingRow.ttc}</td></tr>
                    </tbody>
                  </table>
                </div>

                {/* Panel 3: Vérifications */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <h3 className="font-bold text-slate-800 mb-3">Vérifications</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center"><span className="text-gray-600">ICE Fournisseur valide</span><span className="text-green-500">✔</span></div>
                    <div className="flex justify-between items-center"><span className="text-gray-600">TVA correcte</span><span className="text-green-500">✔</span></div>
                    <div className="flex justify-between items-center"><span className="text-gray-600">Montant cohérent</span><span className="text-green-500">✔</span></div>
                    <div className="flex justify-between items-center text-red-600 font-medium"><span>Doublon détecté</span><span>✖</span></div>
                  </div>
                </div>

              </div>

              {/* Action Buttons[cite: 10] */}
              <div className="p-4 bg-white border-t border-gray-200 flex justify-end gap-3">
                <button className="px-4 py-2 border border-red-200 text-red-600 font-bold rounded-lg hover:bg-red-50 text-sm">Rejeter</button>
                <button className="px-4 py-2 border border-amber-200 text-amber-600 font-bold rounded-lg hover:bg-amber-50 text-sm">Corriger</button>
                <button className="px-4 py-2 bg-green-500 text-white font-bold rounded-lg hover:bg-green-600 text-sm">Valider</button>
                <button className="px-4 py-2 border border-blue-200 text-blue-600 font-bold rounded-lg hover:bg-blue-50 text-sm">Exporter Sage</button>
              </div>
            </div>
          </div>
          
          {/* Bottom Bar (Chronos)[cite: 10] */}
          <div className="h-32 bg-gray-100 border-t border-gray-300 p-4 flex gap-4 overflow-x-auto items-center">
             <div className="text-xs font-bold text-gray-500 w-24">Chronos <br/> {viewingRow.entreprise}</div>
             {achatsData.map(doc => (
                <div key={doc.id} className={`min-w-[180px] bg-white p-3 border ${doc.id === viewingRow.id ? 'border-blue-500 shadow-md' : 'border-gray-200'} rounded-lg flex flex-col justify-between h-full cursor-pointer hover:border-blue-300`} onClick={() => setViewingRow(doc)}>
                  <div className="flex items-start gap-2">
                     <span className="text-gray-400 text-xl">📄</span>
                     <div>
                       <div className="text-xs font-bold truncate w-28">{doc.fichier}</div>
                       <div className="text-[10px] text-gray-500">{doc.date}</div>
                       <div className="font-bold text-sm mt-1">{doc.ttc} DH</div>
                     </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${doc.validation === 'Validé' ? 'text-green-600 bg-green-50' : 'text-amber-600 bg-amber-50'}`}>{doc.validation}</span>
                  </div>
                </div>
             ))}
          </div>
        </div>
      )}
    </div>
  );
}