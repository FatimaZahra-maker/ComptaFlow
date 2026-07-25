import React, { useState } from "react";

// --- MOCK DATA (Pour reproduire visuellement l'image) ---
const MOUVEMENTS_DATA = [
  { id: 1, date: "01/07/2025", libelle: "Virement client CLINIQUE ARGANA", ref: "TRF-1254", type: "Dépôt", depot: "25 000.00", retrait: "-", solde: "125 000.00" },
  { id: 2, date: "02/07/2025", libelle: "Paiement fournisseur CHQ 4587", ref: "CHQ 4587", type: "Retrait", depot: "-", retrait: "8 500.00", solde: "116 500.00" },
  { id: 3, date: "03/07/2025", libelle: "Frais bancaires tenue de compte", ref: "FRAIS-789", type: "Retrait", depot: "-", retrait: "120.00", solde: "116 380.00" },
  { id: 4, date: "05/07/2025", libelle: "Remise de chèque N°9852", ref: "REM-001", type: "Dépôt", depot: "10 200.00", retrait: "-", solde: "126 580.00" },
];

export function RelevesBancairesPage() {
  const [entreprise, setEntreprise] = useState("STE MAROC PIECES AUTO SARL");
  const [annee, setAnnee] = useState("2025");
  const [mois, setMois] = useState("Juillet");

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans">
      
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
            <label className="block text-xs font-medium text-slate-500 mb-1">Entreprise</label>
            <select 
              value={entreprise} 
              onChange={(e) => setEntreprise(e.target.value)}
              className="w-64 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option>{entreprise}</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Année</label>
            <select 
              value={annee} 
              onChange={(e) => setAnnee(e.target.value)}
              className="w-32 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option>2025</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Mois</label>
            <select 
              value={mois} 
              onChange={(e) => setMois(e.target.value)}
              className="w-40 px-3 py-2 bg-white border border-slate-200 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option>Juillet</option>
            </select>
          </div>
        </div>
        
        <div className="flex gap-2">
          <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors">
            <span className="text-lg leading-none">↑</span> Importer un relevé
          </button>
          <button className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 hover:bg-slate-50 transition-colors">
            Exporter <span className="text-xs">▼</span>
          </button>
        </div>
      </div>

      {/* Zone principale : Tableau + Sidebar droite */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        
        {/* Colonne de gauche (Tableau principal) */}
        <div className="xl:col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-xs">Date ▽</th>
                  <th className="px-4 py-3 text-xs">Libellé ▽</th>
                  <th className="px-4 py-3 text-xs">Référence ▽</th>
                  <th className="px-4 py-3 text-xs">Type ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Dépôt ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Retrait ▽</th>
                  <th className="px-4 py-3 text-xs text-right">Solde ▽</th>
                  <th className="px-4 py-3 text-xs text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {MOUVEMENTS_DATA.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-4 text-xs font-medium text-slate-700">{row.date}</td>
                    <td className="px-4 py-4 text-xs text-slate-600 truncate whitespace-normal w-64 leading-tight">{row.libelle}</td>
                    <td className="px-4 py-4 text-xs">{row.ref}</td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded text-xs ${row.type === 'Dépôt' ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-700 border border-red-100'}`}>
                        {row.type}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-xs text-right font-medium text-green-600">{row.depot !== '-' ? `${row.depot} MAD` : '-'}</td>
                    <td className="px-4 py-4 text-xs text-right font-medium text-red-500">{row.retrait !== '-' ? `${row.retrait} MAD` : '-'}</td>
                    <td className="px-4 py-4 text-xs text-right font-bold text-slate-800">{row.solde} MAD</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-center gap-2 text-slate-400">
                        <button className="hover:text-blue-600">✎</button>
                        <button className="hover:text-slate-600">⋮</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Pagination */}
          <div className="border-t border-slate-200 px-4 py-3 flex items-center justify-between bg-slate-50 text-sm">
            <span className="text-slate-500 text-xs">Affichage de 1 à 4 sur 45 résultats</span>
            <div className="flex items-center gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white text-slate-400 disabled:opacity-50" disabled>⟨</button>
              <button className="w-8 h-8 flex items-center justify-center rounded bg-indigo-600 text-white font-medium">1</button>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white hover:bg-slate-50">2</button>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white hover:bg-slate-50">3</button>
              <span className="px-2 text-slate-400">...</span>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">⟩</button>
            </div>
          </div>
        </div>

        {/* Colonne de droite (Navigation + Stats) */}
        <div className="xl:col-span-1 space-y-6">
          
          {/* Types de tableaux */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
            <h3 className="font-semibold text-slate-800 mb-4 text-sm">Types de tableaux</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors">
                <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded flex items-center justify-center">🛒</div>
                <div>
                  <div className="text-sm font-medium text-slate-700">Achats</div>
                  <div className="text-xs text-slate-500">Documents d'achat</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors">
                <div className="w-8 h-8 bg-green-100 text-green-600 rounded flex items-center justify-center">🛍</div>
                <div>
                  <div className="text-sm font-medium text-slate-700">Ventes</div>
                  <div className="text-xs text-slate-500">Documents de vente</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 bg-indigo-50/50 border border-indigo-100 rounded-lg cursor-pointer">
                <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded flex items-center justify-center">🏦</div>
                <div>
                  <div className="text-sm font-medium text-indigo-700">Relevés bancaires</div>
                  <div className="text-xs text-indigo-500">Mouvements bancaires</div>
                </div>
              </div>
            </div>
          </div>

          {/* Calculs & Totaux (Banque) */}
          <div className="bg-orange-50/50 border border-orange-100 rounded-xl shadow-sm p-5">
            <h3 className="font-semibold text-orange-800 mb-4 text-sm">Calculs & Totaux (Juillet)</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm border-b border-orange-100 pb-2">
                <span className="text-slate-600">Total Dépôts</span>
                <span className="font-semibold text-green-700">35 200.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-orange-100 pb-2">
                <span className="text-slate-600">Total Retraits</span>
                <span className="font-semibold text-red-600">8 620.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-orange-100 pb-2">
                <span className="text-slate-600">Solde Initial</span>
                <span className="font-semibold text-slate-800">100 000.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-600">Solde Final</span>
                <span className="font-bold text-slate-900">126 580.00 MAD</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}