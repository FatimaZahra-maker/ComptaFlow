import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

// --- INTERFACES ---
interface MouvementRow {
  id: number;
  date: string;
  libelle: string;
  ref: string;
  type: string;
  depot: string;
  retrait: string;
  solde: string;
  annee: string;
  mois: string;
  entreprise: string;
  fichier: string;
  statut: string;
  validation: string;
}

// --- MOCK DATA ---
const INITIAL_MOUVEMENTS: MouvementRow[] = [
  { id: 1, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Juillet", date: "01/07/2025", libelle: "Virement client CLINIQUE ARGANA", ref: "TRF-1254", type: "Dépôt", depot: "25 000.00", retrait: "-", solde: "125 000.00", fichier: "releve_juillet_25.pdf", statut: "Saisi", validation: "Validé" },
  { id: 2, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Juillet", date: "02/07/2025", libelle: "Paiement fournisseur CHQ 4587", ref: "CHQ 4587", type: "Retrait", depot: "-", retrait: "8 500.00", solde: "116 500.00", fichier: "releve_juillet_25.pdf", statut: "Saisi", validation: "Validé" },
  { id: 3, entreprise: "TECH SOLUTIONS MAROC", annee: "2025", mois: "Juillet", date: "03/07/2025", libelle: "Frais bancaires tenue de compte", ref: "FRAIS-789", type: "Retrait", depot: "-", retrait: "120.00", solde: "116 380.00", fichier: "releve_07_tech.pdf", statut: "À vérifier", validation: "Nouveau" },
  { id: 4, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Juillet", date: "05/07/2025", libelle: "Remise de chèque N°9852", ref: "REM-001", type: "Dépôt", depot: "10 200.00", retrait: "-", solde: "126 580.00", fichier: "releve_juillet_25.pdf", statut: "Saisi", validation: "À vérifier" },
];

export function RelevesBancairesPage() {
  const navigate = useNavigate();

  // --- ÉTATS ---
  const [mouvementsData, setMouvementsData] = useState<MouvementRow[]>(INITIAL_MOUVEMENTS);
  const [entreprise, setEntreprise] = useState("Toutes");
  const [annee, setAnnee] = useState("2025");
  const [mois, setMois] = useState("Tous les mois");

  const [editingRow, setEditingRow] = useState<MouvementRow | null>(null);
  const [viewingRow, setViewingRow] = useState<MouvementRow | null>(null);

  // --- LOGIQUE DE FILTRAGE ---
  const donneesFiltrees = mouvementsData.filter((row) => {
    const matchEntreprise = entreprise === "Toutes" || row.entreprise === entreprise;
    const matchAnnee = annee === "Toutes" || row.annee === annee;
    const matchMois = mois === "Tous les mois" || row.mois === mois;
    return matchEntreprise && matchAnnee && matchMois;
  });

  // --- ACTIONS (ÉDITION) ---
  const handleEdit = (row: MouvementRow) => {
    setEditingRow({ ...row });
  };

  const handleSaveEdit = () => {
    if (editingRow) {
      setMouvementsData(prev => prev.map(item => item.id === editingRow.id ? editingRow : item));
      setEditingRow(null);
    }
  };

  // --- EXPORT EXCEL (CSV) ---
  const handleExport = () => {
    if (donneesFiltrees.length === 0) return alert("Rien à exporter.");
    const headers = ["Entreprise", "Date", "Libellé", "Référence", "Type", "Dépôt", "Retrait", "Solde", "Fichier", "Statut", "Validation"];
    const rows = donneesFiltrees.map(r => [
      `"${r.entreprise}"`, `"${r.date}"`, `"${r.libelle}"`, `"${r.ref}"`, `"${r.type}"`,
      `"${r.depot}"`, `"${r.retrait}"`, `"${r.solde}"`, `"${r.fichier}"`, `"${r.statut}"`, `"${r.validation}"`
    ]);
    const csvContent = [headers.join(";"), ...rows.map(row => row.join(";"))].join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `Export_Banque_${entreprise.replace(/\s/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans relative">
      
      {/* En-tête */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Relevés bancaires <span className="font-normal text-slate-500">— Tableau des mouvements</span>
        </h1>
      </div>

      {/* Barre de filtres et actions */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="flex gap-4">
          <div>
            <label htmlFor="bq-entreprise" className="block text-xs font-bold text-slate-500 mb-1">Entreprise</label>
            <select 
              id="bq-entreprise"
              value={entreprise} 
              onChange={(e) => setEntreprise(e.target.value)}
              className="w-64 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes les entreprises</option>
              <option value="STE MAROC PIECES AUTO SARL">STE MAROC PIECES AUTO SARL</option>
              <option value="TECH SOLUTIONS MAROC">TECH SOLUTIONS MAROC</option>
            </select>
          </div>
          <div>
            <label htmlFor="bq-annee" className="block text-xs font-bold text-slate-500 mb-1">Année</label>
            <select 
              id="bq-annee"
              value={annee} 
              onChange={(e) => setAnnee(e.target.value)}
              className="w-32 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes</option>
              <option value="2025">2025</option>
            </select>
          </div>
          <div>
            <label htmlFor="bq-mois" className="block text-xs font-bold text-slate-500 mb-1">Mois</label>
            <select 
              id="bq-mois"
              value={mois} 
              onChange={(e) => setMois(e.target.value)}
              className="w-40 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer shadow-sm"
            >
              <option value="Tous les mois">Tous les mois</option>
              <option value="Juillet">Juillet</option>
            </select>
          </div>
        </div>
        
        <div className="flex gap-3">
          <button onClick={handleExport} className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 hover:bg-slate-50 transition-colors shadow-sm">
            Exporter vers Excel <span className="text-xs">▼</span>
          </button>
        </div>
      </div>

      {/* Zone principale : Tableau + Sidebar droite */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        
        {/* Colonne de gauche (Tableau principal) */}
        <div className="xl:col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-xs">Fichier ▽</th>
                  <th className="px-4 py-3 text-xs">Date ▽</th>
                  <th className="px-4 py-3 text-xs">Libellé ▽</th>
                  <th className="px-4 py-3 text-xs">Référence ▽</th>
                  <th className="px-4 py-3 text-xs">Type ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Dépôt ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Retrait ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Solde ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Statut ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {donneesFiltrees.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-slate-500 italic">
                      Aucun mouvement trouvé pour ces filtres.
                    </td>
                  </tr>
                ) : (
                  donneesFiltrees.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3">
                        <span onClick={() => setViewingRow(row)} className="text-indigo-600 font-medium text-xs hover:underline cursor-pointer">{row.fichier}</span>
                      </td>
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700">{row.date}</td>
                      <td className="px-4 py-3 text-xs text-slate-600 truncate whitespace-normal w-48 leading-tight">{row.libelle}</td>
                      <td className="px-4 py-3 text-xs font-medium">{row.ref}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded-full text-[11px] font-bold ${row.type === 'Dépôt' ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-700 border border-red-100'}`}>
                          {row.type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-right font-bold text-green-600">{row.depot !== '-' ? `${row.depot}` : '-'}</td>
                      <td className="px-4 py-3 text-xs text-right font-bold text-red-500">{row.retrait !== '-' ? `${row.retrait}` : '-'}</td>
                      <td className="px-4 py-3 text-xs text-right font-bold text-slate-900">{row.solde}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${row.validation === 'Validé' ? 'bg-green-50 text-green-700 border-green-200' : row.validation === 'Nouveau' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                          {row.validation}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-3 text-slate-400 text-base">
                          <button onClick={() => setViewingRow(row)} title="Voir" className="hover:text-indigo-600 transition-colors">👁</button>
                          <button onClick={() => handleEdit(row)} title="Modifier" className="hover:text-amber-500 transition-colors">✎</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          <div className="border-t border-slate-200 px-4 py-3 flex items-center justify-between bg-slate-50/50 text-sm">
            <span className="text-slate-500 text-xs font-medium">Affichage de {donneesFiltrees.length} résultat(s)</span>
          </div>
        </div>

        {/* Colonne de droite (Navigation + Stats) */}
        <div className="xl:col-span-1 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5">
            <h3 className="font-bold text-slate-800 mb-4 text-sm">Types de tableaux</h3>
            <div className="space-y-2">
              <div onClick={() => navigate('/achats')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-blue-50 group-hover:bg-blue-100 group-hover:text-blue-700 text-blue-600 rounded-md flex items-center justify-center text-lg transition-colors">🛒</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-blue-700 transition-colors">Achats</div>
                </div>
              </div>
              <div onClick={() => navigate('/ventes')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-green-50 group-hover:bg-green-100 group-hover:text-green-700 text-green-600 rounded-md flex items-center justify-center text-lg transition-colors">🛍</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-green-700 transition-colors">Ventes</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 bg-indigo-50/70 border border-indigo-100 rounded-lg cursor-default">
                <div className="w-9 h-9 bg-white shadow-sm border border-indigo-100 text-indigo-600 rounded-md flex items-center justify-center text-lg">🏦</div>
                <div>
                  <div className="text-sm font-bold text-indigo-700">Relevés bancaires</div>
                  <div className="text-[11px] font-medium text-indigo-500">Mouvements bancaires</div>
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
              <h2 className="text-lg font-bold text-slate-800">Modifier le mouvement bancaire</h2>
              <button onClick={() => setEditingRow(null)} className="text-slate-400 hover:text-red-500 text-2xl font-bold transition-colors leading-none">&times;</button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Libellé</label>
                <input type="text" value={editingRow.libelle} onChange={(e) => setEditingRow({...editingRow, libelle: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500" />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Référence</label>
                  <input type="text" value={editingRow.ref} onChange={(e) => setEditingRow({...editingRow, ref: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Type</label>
                  <select value={editingRow.type} onChange={(e) => setEditingRow({...editingRow, type: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500">
                    <option value="Dépôt">Dépôt</option>
                    <option value="Retrait">Retrait</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Dépôt</label>
                  <input type="text" value={editingRow.depot} onChange={(e) => setEditingRow({...editingRow, depot: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Retrait</label>
                  <input type="text" value={editingRow.retrait} onChange={(e) => setEditingRow({...editingRow, retrait: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Solde</label>
                  <input type="text" value={editingRow.solde} onChange={(e) => setEditingRow({...editingRow, solde: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-100">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Statut</label>
                  <select value={editingRow.statut} onChange={(e) => setEditingRow({...editingRow, statut: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500">
                    <option value="À vérifier">À vérifier</option>
                    <option value="Saisi">Saisi</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Validation (Chrono)</label>
                  <select value={editingRow.validation} onChange={(e) => setEditingRow({...editingRow, validation: e.target.value})} className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500">
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
              <button onClick={handleSaveEdit} className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700 shadow-sm">Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {/* --- VUE DÉTAILLÉE PLEIN ÉCRAN (ŒIL) --- */}
      {viewingRow && (
        <div className="fixed inset-0 bg-white z-[100] flex flex-col h-screen overflow-hidden text-sm">
          
          {/* Top Bar */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-white shadow-sm shrink-0">
            <div className="flex items-center gap-3">
              <button onClick={() => setViewingRow(null)} className="text-gray-500 hover:text-gray-800 font-bold mr-2 flex items-center gap-1">
                <span>←</span> Retour
              </button>
              <span className="text-gray-400">Relevés /</span>
              <span className="font-bold text-slate-800">Mouvement {viewingRow.ref}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-semibold ml-2 ${viewingRow.validation === 'Validé' ? 'bg-green-100 text-green-700' : 'bg-indigo-50 text-indigo-600'}`}>{viewingRow.validation}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right leading-tight">
                <div className="font-bold text-slate-800">Cabinet Alpha</div>
                <div className="text-xs text-gray-500">Expert-Comptable</div>
              </div>
              <div className="w-8 h-8 bg-indigo-600 rounded-full text-white flex items-center justify-center font-bold">CA</div>
            </div>
          </div>

          {/* Main Content Area */}
          <div className="flex flex-1 overflow-hidden bg-gray-50">
            
            {/* Left side: "PDF" Viewer with fixed scrolling and scaling */}
            <div className="w-7/12 bg-[#323639] flex flex-col relative h-full min-h-0">
              {/* Fake PDF Toolbar */}
              <div className="flex justify-between items-center text-white bg-[#202124] px-4 py-2 text-sm z-10 shadow-md shrink-0">
                <span>Page 1 / 1</span>
                <div className="flex gap-4 items-center">
                  <button className="hover:bg-white/10 px-2 py-1 rounded">-</button>
                  <span>90%</span>
                  <button className="hover:bg-white/10 px-2 py-1 rounded">+</button>
                </div>
                <button className="hover:bg-white/10 px-2 py-1 rounded">⤢</button>
              </div>
              
              {/* Scrollable Document Area */}
              <div className="flex-1 overflow-auto p-4 md:p-8 flex justify-center items-start">
                
                {/* Fake PDF Paper - Bank Statement (Scaled to fit nicely) */}
                <div className="bg-white shadow-2xl w-full max-w-3xl shrink-0 origin-top transform scale-90 transition-transform">
                  <div className="p-10 min-h-[800px]">
                    <div className="flex justify-between items-start mb-10 border-b-2 border-indigo-900 pb-6">
                      <div>
                        <h1 className="text-3xl font-black text-indigo-900 tracking-tight">BANQUE MAROCAINE</h1>
                        <p className="text-gray-500 text-xs mt-1">L'avenir est à vous</p>
                      </div>
                      <div className="text-right">
                        <h2 className="font-bold text-lg">RELEVÉ DE COMPTE</h2>
                        <p className="text-sm">Période : {viewingRow.mois} {viewingRow.annee}</p>
                        <p className="text-sm">Compte N° : 007 780 0000000000123456 89</p>
                      </div>
                    </div>

                    <div className="mb-6">
                      <h3 className="font-bold text-sm mb-1 text-gray-700">Client :</h3>
                      <p className="font-bold text-lg">{viewingRow.entreprise}</p>
                      <p className="text-gray-600 text-sm">Zone Industrielle, Lot 45<br/>Casablanca, Maroc</p>
                    </div>

                    <table className="w-full text-left text-sm border-collapse mt-8">
                      <thead>
                        <tr className="bg-gray-100 text-gray-700">
                          <th className="py-3 px-2 border-b border-gray-300">Date</th>
                          <th className="py-3 px-2 border-b border-gray-300">Libellé de l'opération</th>
                          <th className="py-3 px-2 border-b border-gray-300 text-right">Débit</th>
                          <th className="py-3 px-2 border-b border-gray-300 text-right">Crédit</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b border-gray-200">
                          <td className="py-3 px-2">01/07/2025</td>
                          <td className="py-3 px-2 text-gray-500">SOLDE PRÉCÉDENT</td>
                          <td className="py-3 px-2 text-right"></td>
                          <td className="py-3 px-2 text-right"></td>
                        </tr>
                        {/* Highlighted current transaction */}
                        <tr className="border-b-2 border-indigo-200 bg-indigo-50">
                          <td className="py-3 px-2 font-bold text-indigo-900">{viewingRow.date}</td>
                          <td className="py-3 px-2 font-bold text-indigo-900">{viewingRow.libelle} (Réf: {viewingRow.ref})</td>
                          <td className="py-3 px-2 text-right font-bold text-red-600">{viewingRow.retrait !== '-' ? viewingRow.retrait : ''}</td>
                          <td className="py-3 px-2 text-right font-bold text-green-600">{viewingRow.depot !== '-' ? viewingRow.depot : ''}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>
            </div>

            {/* Right side: Data & Actions */}
            <div className="w-5/12 bg-white border-l border-gray-200 flex flex-col h-full min-h-0">
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                
                {/* Panel 1: Extraction IA */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-slate-800">Informations extraites (IA)</h3>
                    <div className="text-xs text-green-600 font-bold bg-green-50 px-2 py-1 rounded">Confiance : 99%</div>
                  </div>
                  <div className="grid grid-cols-2 gap-y-3 text-sm">
                    <div className="text-gray-500">Date d'opération</div><div className="text-right font-medium">{viewingRow.date}</div>
                    <div className="text-gray-500">Référence</div><div className="text-right font-medium">{viewingRow.ref}</div>
                    <div className="text-gray-500">Type d'opération</div><div className="text-right font-medium">{viewingRow.type}</div>
                    <div className="text-gray-500">Libellé</div><div className="text-right font-medium truncate" title={viewingRow.libelle}>{viewingRow.libelle}</div>
                    <div className="text-gray-500">Montant Débit (Retrait)</div><div className="text-right font-medium text-red-600">{viewingRow.retrait !== '-' ? viewingRow.retrait + ' MAD' : '-'}</div>
                    <div className="text-gray-500">Montant Crédit (Dépôt)</div><div className="text-right font-medium text-green-600">{viewingRow.depot !== '-' ? viewingRow.depot + ' MAD' : '-'}</div>
                  </div>
                </div>

                {/* Panel 2: Compta */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <h3 className="font-bold text-slate-800 mb-4">Écriture comptable générée</h3>
                  <table className="w-full text-xs">
                    <thead className="text-gray-500 border-b border-gray-100">
                      <tr><th className="text-left pb-2">Compte</th><th className="text-left pb-2">Libellé</th><th className="text-right pb-2">Débit</th><th className="text-right pb-2">Crédit</th></tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {viewingRow.type === 'Dépôt' ? (
                        <>
                          <tr><td className="py-2">5141</td><td className="py-2">Banque</td><td className="py-2 text-right">{viewingRow.depot}</td><td className="py-2 text-right">-</td></tr>
                          <tr><td className="py-2">3421</td><td className="py-2">Client (À affecter)</td><td className="py-2 text-right">-</td><td className="py-2 text-right">{viewingRow.depot}</td></tr>
                        </>
                      ) : (
                        <>
                          <tr><td className="py-2">4411</td><td className="py-2">Fournisseur (À affecter)</td><td className="py-2 text-right">{viewingRow.retrait}</td><td className="py-2 text-right">-</td></tr>
                          <tr><td className="py-2">5141</td><td className="py-2">Banque</td><td className="py-2 text-right">-</td><td className="py-2 text-right">{viewingRow.retrait}</td></tr>
                        </>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Panel 3: Vérifications */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4">
                  <h3 className="font-bold text-slate-800 mb-3">Vérifications & Rapprochement</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center"><span className="text-gray-600">Continuité du solde</span><span className="text-green-500">✔</span></div>
                    <div className="flex justify-between items-center"><span className="text-gray-600">Date valide</span><span className="text-green-500">✔</span></div>
                    <div className="flex justify-between items-center"><span className="text-gray-600">Pièce justificative jointe</span><span className="text-amber-500 font-bold">À lier</span></div>
                  </div>
                </div>

              </div>

              {/* Action Buttons */}
              <div className="p-4 bg-white border-t border-gray-200 flex justify-end gap-3 shrink-0">
                <button className="px-4 py-2 border border-red-200 text-red-600 font-bold rounded-lg hover:bg-red-50 text-sm">Rejeter</button>
                <button className="px-4 py-2 border border-amber-200 text-amber-600 font-bold rounded-lg hover:bg-amber-50 text-sm">Modifier</button>
                <button className="px-4 py-2 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 text-sm shadow-sm">Valider Mouvement</button>
              </div>
            </div>
          </div>
          
          {/* Bottom Bar (Chronos) */}
          <div className="h-32 bg-gray-100 border-t border-gray-300 p-4 flex gap-4 overflow-x-auto items-center shrink-0">
             <div className="text-xs font-bold text-gray-500 w-24">Mouvements <br/> {viewingRow.mois}</div>
             {mouvementsData.map(doc => (
                <div key={doc.id} className={`min-w-[200px] bg-white p-3 border ${doc.id === viewingRow.id ? 'border-indigo-500 shadow-md' : 'border-gray-200'} rounded-lg flex flex-col justify-between h-full cursor-pointer hover:border-indigo-300`} onClick={() => setViewingRow(doc)}>
                  <div className="flex items-start gap-2">
                     <span className="text-gray-400 text-xl">🏦</span>
                     <div className="overflow-hidden">
                       <div className="text-xs font-bold truncate w-32">{doc.libelle}</div>
                       <div className="text-[10px] text-gray-500">{doc.date} • {doc.ref}</div>
                       <div className={`font-bold text-sm mt-1 ${doc.type === 'Dépôt' ? 'text-green-600' : 'text-red-600'}`}>
                         {doc.type === 'Dépôt' ? '+' + doc.depot : '-' + doc.retrait} MAD
                       </div>
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