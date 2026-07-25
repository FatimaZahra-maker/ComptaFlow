import React, { useState } from "react";

// --- MOCK DATA (Pour reproduire visuellement l'image) ---
const ACHATS_DATA = [
  { id: 1, entreprise: "STE MAROC PIECES AUTO SARL", type: "pdf", fichier: "fact_achat_0158.pdf", tiers: "STE ELECTROMAR SARL", cat: "Achat", ref: "FA2404-0158", date: "24/04/2024", libelle: "Achat pièces auto", ht: "5 550.00", tva: "1 110.00 (20%)", ttc: "6 660.00", statut: "Saisi", validation: "Validé" },
  { id: 2, entreprise: "STE MAROC PIECES AUTO SARL", type: "png", fichier: "test5.png", tiers: "BATI SERVICES SARL", cat: "Achat", ref: "FS-2025-0789", date: "24/07/2025", libelle: "Fourniture matériel", ht: "18 850.00", tva: "3 770.00 (20%)", ttc: "22 620.00", statut: "Saisi", validation: "Validé" },
  { id: 3, entreprise: "STE MAROC PIECES AUTO SARL", type: "pdf", fichier: "achat_00235.pdf", tiers: "GLOBAL OFFICE SOLUTIONS...", cat: "Achat", ref: "FA2405-00235", date: "23/05/2024", libelle: "Consommables bureau", ht: "24 995.00", tva: "4 999.20 (20%)", ttc: "29 993.20", statut: "Saisi", validation: "À vérifier" },
  { id: 4, entreprise: "STE MAROC PIECES AUTO SARL", type: "xlsx", fichier: "achat_mars.xlsx", tiers: "STE ELECTROMAR SARL", cat: "Achat", ref: "FA2403-0312", date: "15/03/2024", libelle: "Pièces détachées", ht: "7 200.00", tva: "1 440.00 (20%)", ttc: "8 640.00", statut: "Saisi", validation: "Validé" },
];

export function AchatsPage() {
  const [entreprise, setEntreprise] = useState("STE MAROC PIECES AUTO SARL");
  const [annee, setAnnee] = useState("2025");
  const [mois, setMois] = useState("Tous les mois");

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 text-slate-800 font-sans">
      
      {/* En-tête */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Achats <span className="font-normal text-slate-500">— Tableau des documents d'achat</span>
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
              <option>Tous les mois</option>
            </select>
          </div>
        </div>
        
        <div className="flex gap-2">
          <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 transition-colors">
            <span className="text-lg leading-none">↑</span> Importer un document
          </button>
          <button className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 hover:bg-slate-50 transition-colors">
            Exporter <span className="text-xs">▼</span>
          </button>
        </div>
      </div>

      {/* Zone principale : Tableau + Sidebar droite */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        
        {/* Colonne de gauche (Tableau principal) - Prend 3/4 de l'espace */}
        <div className="xl:col-span-3 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-sm text-left whitespace-nowrap">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3 text-xs">Entreprise ▽</th>
                  <th className="px-4 py-3 text-xs">Fichier ▽</th>
                  <th className="px-4 py-3 text-xs">Client / Fournisseur ▽</th>
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
                {ACHATS_DATA.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-4 text-xs font-medium text-slate-700 w-32 truncate whitespace-normal leading-tight">{row.entreprise}</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white ${row.type === 'pdf' ? 'bg-red-500' : row.type === 'png' ? 'bg-blue-500' : 'bg-green-600'}`}>
                          {row.type.toUpperCase()}
                        </span>
                        <span className="text-blue-600 text-xs hover:underline cursor-pointer">{row.fichier}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-xs font-medium whitespace-normal leading-tight w-32">{row.tiers}</td>
                    <td className="px-4 py-4">
                      <span className="bg-blue-50 text-blue-600 border border-blue-100 px-2 py-1 rounded text-xs">
                        {row.cat}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-xs">{row.ref}</td>
                    <td className="px-4 py-4 text-xs">{row.date}</td>
                    <td className="px-4 py-4 text-xs text-slate-500">{row.libelle}</td>
                    <td className="px-4 py-4 text-xs text-right font-medium">{row.ht} MAD</td>
                    <td className="px-4 py-4 text-xs text-right text-slate-500 flex flex-col items-end gap-1">
                       <span>{row.tva.split(' ')[0]} MAD</span>
                       <span className="text-[10px] text-slate-400">({row.tva.split(' ')[1].replace(/[()]/g, '')})</span>
                    </td>
                    <td className="px-4 py-4 text-xs text-right font-semibold">{row.ttc} MAD</td>
                    <td className="px-4 py-4 text-center">
                      <span className="bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded text-xs">{row.statut}</span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={`px-2 py-1 rounded text-xs border ${row.validation === 'Validé' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                        {row.validation}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-center gap-2 text-slate-400">
                        <button className="hover:text-blue-600">👁</button>
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
            <span className="text-slate-500 text-xs">Affichage de 1 à 4 sur 52 résultats</span>
            <div className="flex items-center gap-1">
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white text-slate-400 disabled:opacity-50" disabled>⟨</button>
              <button className="w-8 h-8 flex items-center justify-center rounded bg-blue-600 text-white font-medium">1</button>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white hover:bg-slate-50">2</button>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white hover:bg-slate-50">3</button>
              <span className="px-2 text-slate-400">...</span>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white hover:bg-slate-50">13</button>
              <button className="w-8 h-8 flex items-center justify-center rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">⟩</button>
              <select className="ml-2 border border-slate-200 rounded px-2 py-1.5 bg-white text-xs text-slate-600">
                <option>10 / page</option>
              </select>
            </div>
          </div>
        </div>

        {/* Colonne de droite (Navigation + Stats) */}
        <div className="xl:col-span-1 space-y-6">
          
          {/* Types de tableaux */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
            <h3 className="font-semibold text-slate-800 mb-4 text-sm">Types de tableaux</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-3 p-2 bg-blue-50/50 border border-blue-100 rounded-lg cursor-pointer">
                <div className="w-8 h-8 bg-blue-100 text-blue-600 rounded flex items-center justify-center">🛒</div>
                <div>
                  <div className="text-sm font-medium text-blue-700">Achats</div>
                  <div className="text-xs text-blue-500">Documents d'achat</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors">
                <div className="w-8 h-8 bg-green-100 text-green-600 rounded flex items-center justify-center">🛍</div>
                <div>
                  <div className="text-sm font-medium text-slate-700">Ventes</div>
                  <div className="text-xs text-slate-500">Documents de vente</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-2 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors">
                <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded flex items-center justify-center">🏦</div>
                <div>
                  <div className="text-sm font-medium text-slate-700">Relevés bancaires</div>
                  <div className="text-xs text-slate-500">Mouvements bancaires</div>
                </div>
              </div>
            </div>
          </div>

          {/* Statistiques */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5">
            <h3 className="font-semibold text-slate-800 mb-4 text-sm">Statistiques (2025)</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                <span className="text-slate-500">Total Achats (HT)</span>
                <span className="font-semibold text-slate-800">1 256 850.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                <span className="text-slate-500">Total TVA</span>
                <span className="font-semibold text-slate-800">251 370.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                <span className="text-slate-500">Total TTC</span>
                <span className="font-semibold text-slate-800">1 508 220.00 MAD</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Documents</span>
                <span className="font-semibold text-slate-800">52</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Widgets inférieurs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        
        {/* Widget Ventes */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
          <h3 className="font-medium text-green-700 mb-4 text-sm flex items-center gap-2">
            🛍 Ventes — Tableau des documents de vente
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] text-left">
              <thead className="text-slate-400 border-b border-slate-100">
                <tr>
                  <th className="pb-2 font-medium">Entreprise</th>
                  <th className="pb-2 font-medium">Client</th>
                  <th className="pb-2 font-medium">N° Facture</th>
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium text-right">HT</th>
                  <th className="pb-2 font-medium text-right">TVA</th>
                  <th className="pb-2 font-medium text-right">TTC</th>
                  <th className="pb-2 font-medium text-center">Validation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                <tr>
                  <td className="py-2 text-slate-600 whitespace-nowrap">STE MAROC P...</td>
                  <td className="py-2">CLINIQUE ARGANA</td>
                  <td className="py-2">FV2504-015</td>
                  <td className="py-2">24/04/2025</td>
                  <td className="py-2 text-right">10 000.00</td>
                  <td className="py-2 text-right text-slate-400">2 000.00</td>
                  <td className="py-2 text-right font-medium">12 000.00</td>
                  <td className="py-2 text-center text-green-500">✓</td>
                </tr>
                <tr>
                  <td className="py-2 text-slate-600 whitespace-nowrap">STE MAROC P...</td>
                  <td className="py-2">FIDEU SARL</td>
                  <td className="py-2">FV2505-078</td>
                  <td className="py-2">15/05/2025</td>
                  <td className="py-2 text-right">8 500.00</td>
                  <td className="py-2 text-right text-slate-400">1 700.00</td>
                  <td className="py-2 text-right font-medium">10 200.00</td>
                  <td className="py-2 text-center text-amber-500">⌛</td>
                </tr>
              </tbody>
            </table>
          </div>
          <a href="#" className="text-blue-600 text-xs mt-3 inline-block hover:underline">Voir tous les documents de vente →</a>
        </div>

        {/* Widget Banque */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
          <h3 className="font-medium text-indigo-700 mb-4 text-sm flex items-center gap-2">
            🏦 Relevés bancaires — Tableau des mouvements
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] text-left">
              <thead className="text-slate-400 border-b border-slate-100">
                <tr>
                  <th className="pb-2 font-medium">Date</th>
                  <th className="pb-2 font-medium">Libellé</th>
                  <th className="pb-2 font-medium">Référence</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium text-right">Dépôt</th>
                  <th className="pb-2 font-medium text-right">Retrait</th>
                  <th className="pb-2 font-medium text-right">Solde</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                <tr>
                  <td className="py-2">01/07/2025</td>
                  <td className="py-2 text-slate-600">Virement client</td>
                  <td className="py-2">TRF-1254</td>
                  <td className="py-2 text-green-600">Dépôt</td>
                  <td className="py-2 text-right">25 000.00</td>
                  <td className="py-2 text-right text-slate-400">-</td>
                  <td className="py-2 text-right font-medium">125 000.00</td>
                </tr>
                <tr>
                  <td className="py-2">02/07/2025</td>
                  <td className="py-2 text-slate-600">Paiement fou...</td>
                  <td className="py-2">CHQ 4587</td>
                  <td className="py-2 text-red-500">Retrait</td>
                  <td className="py-2 text-right text-slate-400">-</td>
                  <td className="py-2 text-right">8 500.00</td>
                  <td className="py-2 text-right font-medium">116 500.00</td>
                </tr>
              </tbody>
            </table>
          </div>
          <a href="#" className="text-blue-600 text-xs mt-3 inline-block hover:underline">Voir tous les mouvements bancaires →</a>
        </div>

        {/* Widget Calculs et Totaux */}
        <div className="bg-orange-50/50 border border-orange-100 rounded-xl shadow-sm p-4">
          <h3 className="font-medium text-orange-800 mb-4 text-sm flex items-center gap-2">
            🧮 Calculs & Totaux (Banque)
          </h3>
          <div className="space-y-3 mt-4">
             <div className="flex justify-between text-sm bg-white p-2 rounded shadow-sm border border-orange-50">
                <span className="text-slate-600">Total Dépôts</span>
                <span className="font-semibold text-slate-800">245 600.00 MAD</span>
             </div>
             <div className="flex justify-between text-sm bg-white p-2 rounded shadow-sm border border-orange-50">
                <span className="text-slate-600">Total Retraits</span>
                <span className="font-semibold text-slate-800">129 850.00 MAD</span>
             </div>
             <div className="flex justify-between text-sm bg-white p-2 rounded shadow-sm border border-orange-50">
                <span className="text-slate-600">Solde Initial</span>
                <span className="font-semibold text-slate-800">85 000.00 MAD</span>
             </div>
             <div className="flex justify-between text-sm bg-white p-2 rounded shadow-sm border border-orange-50">
                <span className="text-slate-600">Solde Final</span>
                <span className="font-bold text-slate-900">200 750.00 MAD</span>
             </div>
          </div>
        </div>

      </div>

      {/* Alerte Information */}
      <div className="bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3 rounded-lg flex gap-3 text-sm items-start">
        <span className="text-blue-500 text-lg leading-none">ℹ</span>
        <p>Tous les tableaux sont filtrables par Entreprise, Année et Mois. Les données sont automatiquement classifiées après traitement et peuvent être vérifiées, modifiées et validées.</p>
      </div>

    </div>
  );
}