import React, { useState } from "react";
import { useNavigate } from "react-router-dom"; // Import pour la navigation latérale

// --- INTERFACES ---
interface CnssRow {
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
const INITIAL_CNSS_DATA: CnssRow[] = [
  { id: 1, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Avril", type: "pdf", fichier: "bordereau_cnss_04.pdf", tiers: "CNSS", cat: "CNSS", ref: "BDS-0425", date: "10/05/2025", libelle: "Cotisations Avril 2025", ht: "12 450.00", tva: "0.00 (0%)", ttc: "12 450.00", statut: "Saisi", validation: "Validé" },
  { id: 2, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Mai", type: "pdf", fichier: "recu_paiement_cnss.pdf", tiers: "CNSS", cat: "CNSS", ref: "REC-9982", date: "12/05/2025", libelle: "Reçu paiement cotisations", ht: "12 450.00", tva: "0.00 (0%)", ttc: "12 450.00", statut: "Saisi", validation: "Validé" },
];

export function CnssPage() {
  const navigate = useNavigate();

  // --- ÉTATS (DONNÉES ET FILTRES) ---
  const [cnssData, setCnssData] = useState<CnssRow[]>(INITIAL_CNSS_DATA);
  const [entreprise, setEntreprise] = useState("Toutes");
  const [annee, setAnnee] = useState("2025");
  const [mois, setMois] = useState("Tous les mois");
  const [editingRow, setEditingRow] = useState<CnssRow | null>(null);

  // --- LOGIQUE DE FILTRAGE ---
  const donneesFiltrees = cnssData.filter((row) => {
    const matchEntreprise = entreprise === "Toutes" || row.entreprise === entreprise;
    const matchAnnee = annee === "Toutes" || row.annee === annee;
    const matchMois = mois === "Tous les mois" || row.mois === mois;
    return matchEntreprise && matchAnnee && matchMois;
  });

  // --- ACTIONS (ÉDITION & EXPORT) ---
  const handleEdit = (row: CnssRow) => {
    setEditingRow({ ...row }); // Clone pour modification locale
  };

  const handleSave = () => {
    if (editingRow) {
      setCnssData(prevData => prevData.map(item => item.id === editingRow.id ? editingRow : item));
      setEditingRow(null); 
    }
  };

  const handleView = (fichier: string) => {
    alert(`Affichage de l'aperçu pour le fichier : ${fichier}`);
  };

  const handleExport = () => {
    if (donneesFiltrees.length === 0) return alert("Rien à exporter.");
    const headers = ["Entreprise", "Fichier", "Organisme", "Catégorie", "N° Bordereau", "Date", "Libellé", "Montant HT", "TVA", "Montant Total", "Statut", "Validation"];
    const rows = donneesFiltrees.map(r => [
      `"${r.entreprise}"`, `"${r.fichier}"`, `"${r.tiers}"`, `"${r.cat}"`, `"${r.ref}"`, `"${r.date}"`, `"${r.libelle}"`,
      `"${r.ht}"`, `"${r.tva.split(' ')[0]}"`, `"${r.ttc}"`, `"${r.statut}"`, `"${r.validation}"`
    ]);
    const csvContent = [headers.join(";"), ...rows.map(row => row.join(";"))].join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `Export_CNSS_${entreprise.replace(/\s/g, '_')}_${mois}_${annee}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans relative">
      
      {/* En-tête */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          CNSS <span className="font-normal text-slate-500">— Déclarations et cotisations sociales</span>
        </h1>
      </div>

      {/* Filtres et Actions */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="flex gap-4">
          <div>
            <label htmlFor="cnss-entreprise" className="block text-xs font-bold text-slate-500 mb-1">Entreprise</label>
            <select 
              id="cnss-entreprise"
              value={entreprise} 
              onChange={(e) => setEntreprise(e.target.value)}
              className="w-64 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes les entreprises</option>
              <option value="STE MAROC PIECES AUTO SARL">STE MAROC PIECES AUTO SARL</option>
            </select>
          </div>
          <div>
            <label htmlFor="cnss-annee" className="block text-xs font-bold text-slate-500 mb-1">Année</label>
            <select 
              id="cnss-annee"
              value={annee} 
              onChange={(e) => setAnnee(e.target.value)}
              className="w-32 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500 cursor-pointer shadow-sm"
            >
              <option value="Toutes">Toutes</option>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
            </select>
          </div>
          <div>
            <label htmlFor="cnss-mois" className="block text-xs font-bold text-slate-500 mb-1">Mois</label>
            <select 
              id="cnss-mois"
              value={mois} 
              onChange={(e) => setMois(e.target.value)}
              className="w-40 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500 cursor-pointer shadow-sm"
            >
              <option value="Tous les mois">Tous les mois</option>
              <option value="Avril">Avril</option>
              <option value="Mai">Mai</option>
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
                  <th className="px-4 py-3 text-xs">Entreprise ▽</th>
                  <th className="px-4 py-3 text-xs">Fichier ▽</th>
                  <th className="px-4 py-3 text-xs">Organisme ▽</th>
                  <th className="px-4 py-3 text-xs">Catégorie ▽</th>
                  <th className="px-4 py-3 text-xs">N° Bordereau ▽</th>
                  <th className="px-4 py-3 text-xs">Date ▽</th>
                  <th className="px-4 py-3 text-xs">Libellé ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Montant HT ▽</th>
                  <th className="px-4 py-3 text-xs text-right">TVA ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Montant Total ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Statut ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Validation ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {donneesFiltrees.length === 0 ? (
                  <tr>
                    <td colSpan={13} className="px-4 py-8 text-center text-slate-500 italic">
                      Aucun document trouvé pour ces filtres.
                    </td>
                  </tr>
                ) : (
                  donneesFiltrees.map((row) => (
                    <tr key={row.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3 text-xs font-semibold text-slate-700 w-32 truncate whitespace-normal leading-tight">{row.entreprise}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold text-white bg-red-500 shadow-sm">
                            {row.type.toUpperCase()}
                          </span>
                          <span onClick={() => handleView(row.fichier)} className="text-fuchsia-600 font-medium text-xs hover:underline cursor-pointer">
                            {row.fichier}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs font-bold whitespace-normal leading-tight w-32">{row.tiers}</td>
                      <td className="px-4 py-3">
                        <span className="bg-fuchsia-50 text-fuchsia-700 font-medium border border-fuchsia-100 px-2 py-1 rounded text-[11px]">
                          {row.cat}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs">{row.ref}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{row.date}</td>
                      <td className="px-4 py-3 text-xs text-slate-500 w-48 truncate">{row.libelle}</td>
                      <td className="px-4 py-3 text-xs text-right font-medium">{row.ht} MAD</td>
                      <td className="px-4 py-3 text-xs text-right text-slate-500 flex flex-col items-end gap-0.5">
                          <span>{row.tva.split(' ')[0]} MAD</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-right font-bold text-slate-800">{row.ttc} MAD</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${row.statut === 'Saisi' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-slate-100 text-slate-600 border-slate-300'}`}>
                          {row.statut}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-medium border ${row.validation === 'Validé' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                          {row.validation}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-3 text-slate-400 text-base">
                          <button onClick={() => handleView(row.fichier)} title="Voir" className="hover:text-fuchsia-600 transition-colors">👁</button>
                          <button onClick={() => handleEdit(row)} title="Modifier" className="hover:text-amber-500 transition-colors">✎</button>
                          <button title="Options" className="hover:text-slate-700 transition-colors">⋮</button>
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

        {/* Colonne de droite (Navigation) */}
        <div className="xl:col-span-1 space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5">
            <h3 className="font-bold text-slate-800 mb-4 text-sm">Types de tableaux</h3>
            <div className="space-y-2">
              <div onClick={() => navigate('/achats')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-blue-50 group-hover:bg-blue-100 group-hover:text-blue-700 text-blue-600 rounded-md flex items-center justify-center text-lg transition-colors">🛒</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-blue-700 transition-colors">Achats</div>
                  <div className="text-[11px] font-medium text-slate-500 group-hover:text-blue-600 transition-colors">Documents d'achat</div>
                </div>
              </div>
              <div onClick={() => navigate('/ventes')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-green-50 group-hover:bg-green-100 group-hover:text-green-700 text-green-600 rounded-md flex items-center justify-center text-lg transition-colors">🛍</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-green-700 transition-colors">Ventes</div>
                  <div className="text-[11px] font-medium text-slate-500 group-hover:text-green-600 transition-colors">Documents de vente</div>
                </div>
              </div>
              <div onClick={() => navigate('/banque')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-indigo-50 group-hover:bg-indigo-100 group-hover:text-indigo-700 text-indigo-600 rounded-md flex items-center justify-center text-lg transition-colors">🏦</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-indigo-700 transition-colors">Relevés bancaires</div>
                  <div className="text-[11px] font-medium text-slate-500 group-hover:text-indigo-600 transition-colors">Mouvements bancaires</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 bg-fuchsia-50/70 border border-fuchsia-100 rounded-lg cursor-default">
                <div className="w-9 h-9 bg-white shadow-sm border border-fuchsia-100 text-fuchsia-600 rounded-md flex items-center justify-center text-lg">📄</div>
                <div>
                  <div className="text-sm font-bold text-fuchsia-700">CNSS</div>
                  <div className="text-[11px] font-medium text-fuchsia-500">Déclarations sociales</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- FENÊTRE MODALE DE MODIFICATION --- */}
      {editingRow && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-fade-in-up">
            
            <div className="flex justify-between items-center mb-5 border-b border-gray-100 pb-3">
              <h2 className="text-lg font-bold text-slate-800">Modifier le document</h2>
              <button onClick={() => setEditingRow(null)} className="text-slate-400 hover:text-red-500 text-2xl font-bold transition-colors leading-none">&times;</button>
            </div>

            <div className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1">Fichier (Lecture seule)</label>
                <input type="text" value={editingRow.fichier} disabled className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-500 font-medium" />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="edit-ttc" className="block text-xs font-bold text-slate-700 mb-1">Montant Total</label>
                  <input 
                    id="edit-ttc"
                    type="text" 
                    value={editingRow.ttc} 
                    onChange={(e) => setEditingRow({...editingRow, ttc: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/30 focus:border-fuchsia-500 transition-colors" 
                  />
                </div>
                <div>
                  <label htmlFor="edit-tiers" className="block text-xs font-bold text-slate-700 mb-1">Organisme</label>
                  <input 
                    id="edit-tiers"
                    type="text" 
                    value={editingRow.tiers} 
                    onChange={(e) => setEditingRow({...editingRow, tiers: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/30 focus:border-fuchsia-500 transition-colors" 
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-100">
                <div>
                  <label htmlFor="edit-statut" className="block text-xs font-bold text-slate-700 mb-1">Statut</label>
                  <select 
                    id="edit-statut"
                    value={editingRow.statut} 
                    onChange={(e) => setEditingRow({...editingRow, statut: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/30 focus:border-fuchsia-500 cursor-pointer transition-colors"
                  >
                    <option value="En cours">En cours</option>
                    <option value="Saisi">Saisi</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="edit-validation" className="block text-xs font-bold text-slate-700 mb-1">Validation</label>
                  <select 
                    id="edit-validation"
                    value={editingRow.validation} 
                    onChange={(e) => setEditingRow({...editingRow, validation: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-500/30 focus:border-fuchsia-500 cursor-pointer transition-colors"
                  >
                    <option value="À vérifier">À vérifier</option>
                    <option value="Validé">Validé</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-8 pt-4 border-t border-slate-100">
              <button 
                onClick={() => setEditingRow(null)}
                className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Annuler
              </button>
              <button 
                onClick={handleSave}
                className="px-5 py-2 bg-fuchsia-600 text-white rounded-lg text-sm font-bold hover:bg-fuchsia-700 transition-colors shadow-sm"
              >
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}