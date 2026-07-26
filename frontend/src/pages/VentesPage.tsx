import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

// --- INTERFACES ---
interface VenteRow {
  id: number; 
  entreprise: string; 
  annee: string; 
  mois: string; 
  type: string; 
  fichier: string;
  client: string; 
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
const INITIAL_VENTES_DATA: VenteRow[] = [
  { id: 1, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Avril", type: "pdf", fichier: "fact_vente_015.pdf", client: "CLINIQUE ARGANA", cat: "Vente", ref: "FV2504-015", date: "24/04/2025", libelle: "Prestation de service", ht: "10 000.00", tva: "2 000.00 (20%)", ttc: "12 000.00", statut: "Saisi", validation: "Validé" },
  { id: 2, entreprise: "STE MAROC PIECES AUTO SARL", annee: "2025", mois: "Mai", type: "pdf", fichier: "fact_vente_078.pdf", client: "FIDEU SARL", cat: "Vente", ref: "FV2505-078", date: "15/05/2025", libelle: "Vente marchandises", ht: "8 500.00", tva: "1 700.00 (20%)", ttc: "10 200.00", statut: "En cours", validation: "À vérifier" },
  { id: 3, entreprise: "AUTRE ENTREPRISE SA", annee: "2025", mois: "Juin", type: "xlsx", fichier: "export_ventes_juin.xlsx", client: "FREE SAS", cat: "Vente", ref: "FV2506-120", date: "02/06/2025", libelle: "Abonnement annuel", ht: "15 300.00", tva: "3 060.00 (20%)", ttc: "18 360.00", statut: "Saisi", validation: "Validé" },
];

export function VentesPage() {
  const navigate = useNavigate();

  // --- ÉTATS ---
  const [ventesData, setVentesData] = useState<VenteRow[]>(INITIAL_VENTES_DATA);
  const [entreprise, setEntreprise] = useState("Toutes");
  const [annee, setAnnee] = useState("2025");
  const [mois, setMois] = useState("Tous les mois");
  const [editingRow, setEditingRow] = useState<VenteRow | null>(null);
  
  // NOUVEL ÉTAT : Pour la vue plein écran du document
  const [viewingRow, setViewingRow] = useState<VenteRow | null>(null);

  // --- LOGIQUE DE FILTRAGE ---
  const donneesFiltrees = ventesData.filter((row) => {
    const matchEntreprise = entreprise === "Toutes" || row.entreprise === entreprise;
    const matchAnnee = annee === "Toutes" || row.annee === annee;
    const matchMois = mois === "Tous les mois" || row.mois === mois;
    return matchEntreprise && matchAnnee && matchMois;
  });

  // --- ACTIONS (ÉDITION, LECTURE & EXPORT) ---
  const handleEdit = (row: VenteRow) => {
    setEditingRow({ ...row }); // On clone l'objet pour la modification locale
  };

  const handleSave = () => {
    if (editingRow) {
      setVentesData(prevData => prevData.map(item => item.id === editingRow.id ? editingRow : item));
      setEditingRow(null); 
    }
  };

  // MODIFIÉ : Ouvre le lecteur de document au lieu de l'alerte
  const handleView = (row: VenteRow) => {
    setViewingRow(row);
  };

  const handleExport = () => {
    if (donneesFiltrees.length === 0) return alert("Il n'y a aucune donnée à exporter.");
    const headers = ["Entreprise", "Fichier", "Client", "Catégorie", "N° Facture", "Date", "Libellé", "Montant HT (MAD)", "TVA (MAD)", "Montant TTC (MAD)", "Statut", "Validation"];
    const rows = donneesFiltrees.map(row => [
      `"${row.entreprise}"`, `"${row.fichier}"`, `"${row.client}"`, `"${row.cat}"`, `"${row.ref}"`, `"${row.date}"`, `"${row.libelle}"`,
      `"${row.ht.replace(/\s/g, '')}"`, `"${row.tva.split(' ')[0].replace(/\s/g, '')}"`, `"${row.ttc.replace(/\s/g, '')}"`, `"${row.statut}"`, `"${row.validation}"`
    ]);
    const csvContent = [headers.join(";"), ...rows.map(row => row.join(";"))].join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `Export_Ventes_${entreprise.replace(/\s/g, '_')}_${mois}_${annee}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans relative">
      
      {/* En-tête */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Ventes <span className="font-normal text-slate-500">— Tableau des documents de vente</span>
        </h1>
      </div>

      {/* Barre de filtres et actions */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="flex gap-4">
          <div>
            <label htmlFor="vente-entreprise" className="block text-xs font-bold text-slate-500 mb-1">Entreprise</label>
            <select id="vente-entreprise" value={entreprise} onChange={(e) => setEntreprise(e.target.value)} className="w-64 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-green-500 cursor-pointer shadow-sm">
              <option value="Toutes">Toutes les entreprises</option>
              <option value="STE MAROC PIECES AUTO SARL">STE MAROC PIECES AUTO SARL</option>
              <option value="AUTRE ENTREPRISE SA">AUTRE ENTREPRISE SA</option>
            </select>
          </div>
          <div>
            <label htmlFor="vente-annee" className="block text-xs font-bold text-slate-500 mb-1">Année</label>
            <select id="vente-annee" value={annee} onChange={(e) => setAnnee(e.target.value)} className="w-32 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-green-500 cursor-pointer shadow-sm">
              <option value="Toutes">Toutes</option>
              <option value="2025">2025</option>
              <option value="2024">2024</option>
            </select>
          </div>
          <div>
            <label htmlFor="vente-mois" className="block text-xs font-bold text-slate-500 mb-1">Mois</label>
            <select id="vente-mois" value={mois} onChange={(e) => setMois(e.target.value)} className="w-40 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-green-500 cursor-pointer shadow-sm">
              <option value="Tous les mois">Tous les mois</option>
              <option value="Avril">Avril</option>
              <option value="Mai">Mai</option>
              <option value="Juin">Juin</option>
            </select>
          </div>
        </div>
        
        <div className="flex gap-3">
          <button className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-colors shadow-sm">
            <span className="text-lg leading-none">↑</span> Importer
          </button>
          <button onClick={handleExport} className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 hover:bg-slate-50 transition-colors shadow-sm">
            Exporter vers Excel <span className="text-xs">▼</span>
          </button>
        </div>
      </div>

      {/* Zone principale */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        
        {/* Tableau principal */}
        <div className="xl:col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-xs">Entreprise ▽</th>
                  <th className="px-4 py-3 text-xs">Fichier ▽</th>
                  <th className="px-4 py-3 text-xs">Client ▽</th>
                  <th className="px-4 py-3 text-xs">Catégorie ▽</th>
                  <th className="px-4 py-3 text-xs">N° Facture ▽</th>
                  <th className="px-4 py-3 text-xs">Date ▽</th>
                  <th className="px-4 py-3 text-xs">Libellé ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Montant HT ▽</th>
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
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white shadow-sm ${row.type === 'pdf' ? 'bg-red-500' : 'bg-green-600'}`}>
                            {row.type.toUpperCase()}
                          </span>
                          {/* MODIFIÉ : Utilisation de handleView avec l'objet complet `row` */}
                          <span onClick={() => handleView(row)} className="text-green-600 font-medium text-xs hover:underline cursor-pointer">
                            {row.fichier}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs font-bold whitespace-normal leading-tight w-32">{row.client}</td>
                      <td className="px-4 py-3">
                        <span className="bg-green-50 text-green-700 font-medium border border-green-100 px-2 py-1 rounded text-[11px]">{row.cat}</span>
                      </td>
                      <td className="px-4 py-3 text-xs">{row.ref}</td>
                      <td className="px-4 py-3 text-xs text-slate-600">{row.date}</td>
                      <td className="px-4 py-3 text-xs text-slate-500 w-48 truncate">{row.libelle}</td>
                      <td className="px-4 py-3 text-xs text-right font-medium">{row.ht} MAD</td>
                      <td className="px-4 py-3 text-xs text-right text-slate-500 flex flex-col items-end gap-0.5">
                         <span>{row.tva.split(' ')[0]} MAD</span>
                         <span className="text-[10px] text-slate-400 font-medium">({row.tva.split(' ')[1]?.replace(/[()]/g, '') || '20%'})</span>
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
                          {/* MODIFIÉ : Clic sur l'œil */}
                          <button onClick={() => handleView(row)} title="Voir" className="hover:text-green-600 transition-colors">👁</button>
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
              <div className="flex items-center gap-3 p-2 bg-green-50/70 border border-green-100 rounded-lg cursor-default">
                <div className="w-9 h-9 bg-white shadow-sm border border-green-100 text-green-600 rounded-md flex items-center justify-center text-lg">🛍</div>
                <div>
                  <div className="text-sm font-bold text-green-700">Ventes</div>
                  <div className="text-[11px] font-medium text-green-500">Documents de vente</div>
                </div>
              </div>
              <div onClick={() => navigate('/banque')} className="flex items-center gap-3 p-2 hover:bg-slate-50 border border-transparent rounded-lg cursor-pointer transition-colors group">
                <div className="w-9 h-9 bg-indigo-50 group-hover:bg-indigo-100 group-hover:text-indigo-700 text-indigo-600 rounded-md flex items-center justify-center text-lg transition-colors">🏦</div>
                <div>
                  <div className="text-sm font-semibold text-slate-700 group-hover:text-indigo-700 transition-colors">Relevés bancaires</div>
                  <div className="text-[11px] font-medium text-slate-500 group-hover:text-indigo-600 transition-colors">Mouvements bancaires</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- FENÊTRE MODALE DE MODIFICATION --- */}
      {editingRow && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-[60] p-4">
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
                  <label htmlFor="edit-ttc" className="block text-xs font-bold text-slate-700 mb-1">Montant TTC</label>
                  <input 
                    id="edit-ttc"
                    type="text" 
                    value={editingRow.ttc} 
                    onChange={(e) => setEditingRow({...editingRow, ttc: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500 transition-colors" 
                  />
                </div>
                <div>
                  <label htmlFor="edit-client" className="block text-xs font-bold text-slate-700 mb-1">Client</label>
                  <input 
                    id="edit-client"
                    type="text" 
                    value={editingRow.client} 
                    onChange={(e) => setEditingRow({...editingRow, client: e.target.value})}
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500 transition-colors" 
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
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500 cursor-pointer transition-colors"
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
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500 cursor-pointer transition-colors"
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
                className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-bold hover:bg-green-700 transition-colors shadow-sm"
              >
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- VUE DÉTAILLÉE PLEIN ÉCRAN (LE LECTEUR PDF) --- */}
      {viewingRow && (
        <div className="fixed inset-0 bg-zinc-900 z-[100] flex flex-col h-screen overflow-hidden text-sm font-sans">
          
          {/* Header sombre façon lecteur PDF */}
          <div className="flex items-center justify-between px-4 py-3 bg-zinc-800 text-zinc-300 border-b border-zinc-700 shadow-md">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setViewingRow(null)} 
                className="hover:text-white flex items-center gap-2 bg-zinc-700/50 hover:bg-zinc-700 px-3 py-1.5 rounded transition-colors"
              >
                <span>←</span> Retour
              </button>
              <span className="font-semibold text-white tracking-wide">{viewingRow.fichier}</span>
            </div>
            <div className="flex items-center gap-6">
              <span className="text-zinc-400">Page 1 / 1</span>
              <div className="flex items-center gap-3 bg-zinc-900/80 px-3 py-1.5 rounded text-zinc-300 border border-zinc-700">
                <button className="hover:text-white font-bold px-1 transition-colors">-</button>
                <span className="w-10 text-center text-xs font-mono">90%</span>
                <button className="hover:text-white font-bold px-1 transition-colors">+</button>
              </div>
            </div>
          </div>

          {/* ZONE DE DÉFILEMENT (C'est ici qu'apparaît la barre encadrée en rouge) */}
          <div className="flex-1 overflow-auto p-4 md:p-8 flex justify-center items-start custom-scrollbar">
            
            {/* Le document blanc central (La fausse facture) */}
            <div className="bg-white min-h-[800px] w-full max-w-4xl shadow-2xl p-8 md:p-14 text-slate-800 relative">
              
              {/* En-tête du document */}
              <div className="flex justify-between items-start mb-16 border-b border-slate-200 pb-8">
                <div>
                  <h1 className="text-4xl font-black text-slate-900 mb-2 uppercase tracking-tight">Facture</h1>
                  <p className="text-slate-500 font-medium">N° {viewingRow.ref}</p>
                  <p className="text-slate-500">Date d'émission : <span className="text-slate-800 font-medium">{viewingRow.date}</span></p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-xl text-slate-900 mb-1">{viewingRow.entreprise}</p>
                  <p className="text-slate-500 mt-4 text-sm">Facturé à :</p>
                  <p className="font-bold text-lg text-slate-800">{viewingRow.client}</p>
                </div>
              </div>

              {/* Tableau des lignes de la facture */}
              <div className="mb-12">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b-2 border-slate-200">
                      <th className="py-3 px-4 font-bold text-slate-700 uppercase text-xs">Description</th>
                      <th className="py-3 px-4 font-bold text-slate-700 uppercase text-xs w-32 text-center">Quantité</th>
                      <th className="py-3 px-4 font-bold text-slate-700 uppercase text-xs w-40 text-right">Montant HT</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-100">
                      <td className="py-5 px-4">
                        <p className="font-semibold text-slate-800">{viewingRow.libelle}</p>
                        <p className="text-xs text-slate-500 mt-1">Réf. dossier / commande interne</p>
                      </td>
                      <td className="py-5 px-4 text-center text-slate-600">1</td>
                      <td className="py-5 px-4 text-right font-medium text-slate-800">{viewingRow.ht} MAD</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Résumé des totaux */}
              <div className="flex justify-end">
                <div className="w-72 bg-slate-50 p-6 rounded-lg border border-slate-100">
                  <div className="flex justify-between mb-3 text-slate-600">
                    <span>Total HT</span>
                    <span className="font-medium">{viewingRow.ht} MAD</span>
                  </div>
                  <div className="flex justify-between mb-4 text-slate-600">
                    <span>TVA {viewingRow.tva.includes('20%') ? '(20%)' : ''}</span>
                    <span className="font-medium">{viewingRow.tva.split(' ')[0]} MAD</span>
                  </div>
                  <div className="flex justify-between items-center pt-4 border-t-2 border-slate-200">
                    <span className="font-bold text-slate-900 uppercase">Total TTC</span>
                    <span className="font-black text-xl text-green-600">{viewingRow.ttc} MAD</span>
                  </div>
                </div>
              </div>
              
              {/* Pied de page du document */}
              <div className="absolute bottom-8 left-0 right-0 text-center text-xs text-slate-400">
                <p>{viewingRow.entreprise} - Document généré automatiquement</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}