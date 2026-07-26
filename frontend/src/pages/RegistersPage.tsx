import { useState } from "react";
import {
  Search,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  FileText,
  Pencil,
  XCircle,
  MoreHorizontal,
  X,
  Sparkles,
  Trash2,
  Info,
  Download,
  RefreshCw,
  Clock3,
  UserRound,
  UserCog,
  CircleCheckBig,
} from "lucide-react";

// ============================================================================
// TYPES & DONNÉES DE DÉMO
// À remplacer par un vrai appel API (ex: GET /entreprises?statut=en_attente)
// ============================================================================

type Statut = "a_verifier" | "a_completer" | "rejete" | "valide";
type TypeEntite = "Fournisseur" | "Client";

interface EntrepriseRow {
  id: string;
  initiales: string;
  avatarColor: string;
  nom: string;
  type: TypeEntite;
  ice: string | null;
  ifNumber: string | null;
  rc: string | null;
  source: string;
  montantTTC: number;
  extraitLe: string;
  extraitA: string;
  statut: Statut;
  adresse?: string;
  telephone?: string;
  email?: string;
}

const ROWS: EntrepriseRow[] = [
  {
    id: "1",
    initiales: "SE",
    avatarColor: "bg-indigo-100 text-indigo-700",
    nom: "STE ELECTROMAR SARL",
    type: "Fournisseur",
    ice: "001234567890123",
    ifNumber: "34567890",
    rc: "123456",
    source: "facture_achat_001.pdf",
    montantTTC: 6660.0,
    extraitLe: "24/07/2026",
    extraitA: "10:24",
    statut: "a_verifier",
    adresse: "123, Zone Industrielle Sidi Bernoussi\nCasablanca - Maroc",
    telephone: "0522 77 85 40",
    email: "contact@electromar.ma",
  },
  {
    id: "2",
    initiales: "EO",
    avatarColor: "bg-violet-100 text-violet-700",
    nom: "EL OMARI ABDELMONAIM",
    type: "Fournisseur",
    ice: "002345678901234",
    ifNumber: "87654321",
    rc: "987654",
    source: "facture_achat_002.pdf",
    montantTTC: 362.71,
    extraitLe: "24/07/2026",
    extraitA: "10:18",
    statut: "a_verifier",
  },
  {
    id: "3",
    initiales: "CT",
    avatarColor: "bg-slate-200 text-slate-700",
    nom: "CLIENT TEST S.A.",
    type: "Client",
    ice: "003456789012345",
    ifNumber: "98765432",
    rc: "456789",
    source: "facture_vente_001.pdf",
    montantTTC: 23640.0,
    extraitLe: "24/07/2026",
    extraitA: "09:57",
    statut: "a_completer",
  },
  {
    id: "4",
    initiales: "PN",
    avatarColor: "bg-slate-200 text-slate-700",
    nom: "PRENOM NOM",
    type: "Fournisseur",
    ice: null,
    ifNumber: null,
    rc: null,
    source: "facture_achat_003.pdf",
    montantTTC: 48938.25,
    extraitLe: "24/07/2026",
    extraitA: "09:41",
    statut: "a_completer",
  },
  {
    id: "5",
    initiales: "LT",
    avatarColor: "bg-teal-100 text-teal-700",
    nom: "Lugar Travaux SARL AU",
    type: "Fournisseur",
    ice: "004567123456",
    ifNumber: "12345678",
    rc: "654321",
    source: "facture_achat_004.pdf",
    montantTTC: 389800.0,
    extraitLe: "24/07/2026",
    extraitA: "09:12",
    statut: "a_verifier",
  },
  {
    id: "6",
    initiales: "CA",
    avatarColor: "bg-slate-200 text-slate-700",
    nom: "COMPAGNIE ABC",
    type: "Fournisseur",
    ice: "005678901234567",
    ifNumber: "23456789",
    rc: "789123",
    source: "releve_bancaire_001.pdf",
    montantTTC: 885.0,
    extraitLe: "24/07/2026",
    extraitA: "08:55",
    statut: "a_verifier",
  },
  {
    id: "7",
    initiales: "SE",
    avatarColor: "bg-slate-200 text-slate-700",
    nom: "SEIGNE Eric",
    type: "Fournisseur",
    ice: null,
    ifNumber: null,
    rc: null,
    source: "facture_achat_005.pdf",
    montantTTC: 29.99,
    extraitLe: "24/07/2026",
    extraitA: "08:33",
    statut: "a_completer",
  },
];

const STATUT_STYLES: Record<Statut, { label: string; className: string }> = {
  a_verifier: { label: "À vérifier", className: "bg-orange-100 text-orange-700" },
  a_completer: { label: "À compléter", className: "bg-slate-200 text-slate-600" },
  rejete: { label: "Rejeté", className: "bg-red-100 text-red-700" },
  valide: { label: "Validé", className: "bg-emerald-100 text-emerald-700" },
};

const money = (n: number) =>
  `${n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`;

// ============================================================================
// CARTES DE STATISTIQUES
// ============================================================================

function StatCard({
  icon: Icon,
  iconBg,
  iconColor,
  value,
  label,
  caption,
}: {
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  value: string | number;
  label: string;
  caption: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-3">
      <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${iconBg}`}>
        <Icon size={20} className={iconColor} />
      </div>
      <div>
        <p className="text-xl font-bold text-slate-900 leading-tight">{value}</p>
        <p className="text-sm font-medium text-slate-700 leading-tight">{label}</p>
        <p className="text-xs text-slate-400">{caption}</p>
      </div>
    </div>
  );
}

// ============================================================================
// PANNEAU LATÉRAL DE DÉTAIL
// ============================================================================

function Field({ label, value, required = false }: { label: string; value: string; required?: boolean }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      <div className="w-full text-sm text-slate-800 border border-slate-200 rounded-lg px-3 py-2 bg-white whitespace-pre-line">
        {value || "—"}
      </div>
    </div>
  );
}

function DetailPanel({ row, onClose }: { row: EntrepriseRow; onClose: () => void }) {
  const [tab, setTab] = useState<"info" | "docs" | "hist">("info");
  const statut = STATUT_STYLES[row.statut];

  return (
    <aside className="w-[380px] shrink-0 bg-white rounded-xl border border-slate-200 shadow-sm h-fit">
      <div className="flex items-start justify-between p-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold ${row.avatarColor}`}
          >
            {row.initiales}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-slate-900">{row.nom}</p>
              <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${statut.className}`}>
                {statut.label}
              </span>
            </div>
            <p className="text-xs text-slate-400">{row.type}</p>
          </div>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
          <X size={18} />
        </button>
      </div>

      <div className="flex items-center gap-5 px-4 border-b border-slate-100 text-sm">
        {[
          { id: "info", label: "Informations" },
          { id: "docs", label: "Documents (2)" },
          { id: "hist", label: "Historique" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as typeof tab)}
            className={`py-3 border-b-2 font-medium transition-colors ${
              tab === t.id
                ? "border-emerald-600 text-emerald-600"
                : "border-transparent text-slate-400 hover:text-slate-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "info" && (
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-800">Informations extraites</p>
            <button type="button" className="text-slate-400 hover:text-slate-600">
              <Pencil size={15} />
            </button>
          </div>

          <Field label="Nom de l'entreprise" value={row.nom} required />
          <Field label="Type" value={row.type} required />
          <Field label="ICE" value={row.ice ?? ""} />
          <Field label="IF" value={row.ifNumber ?? ""} />
          <Field label="RC" value={row.rc ?? ""} />
          <Field label="Adresse" value={row.adresse ?? ""} />
          <Field label="Téléphone" value={row.telephone ?? ""} />
          <Field label="Email" value={row.email ?? ""} />
          <Field label="Montant TTC" value={money(row.montantTTC)} />
          <Field label="Source" value={row.source} />
          <Field label="Extrait le" value={`${row.extraitLe} à ${row.extraitA}`} />

          <div>
            <p className="text-sm font-semibold text-slate-800 mb-3">Actions</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg py-2.5 transition-colors"
              >
                <CircleCheckBig size={16} />
                Valider
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg py-2.5 transition-colors"
              >
                <XCircle size={16} />
                Rejeter
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-2 border border-amber-300 text-amber-700 hover:bg-amber-50 text-sm font-medium rounded-lg py-2.5 transition-colors"
              >
                <Sparkles size={16} />
                Retraiter avec l'IA
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-2 border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm font-medium rounded-lg py-2.5 transition-colors"
              >
                <Trash2 size={16} />
                Supprimer
              </button>
            </div>
          </div>

          <div className="flex gap-2 bg-sky-50 text-sky-800 text-xs rounded-lg p-3">
            <Info size={15} className="shrink-0 mt-0.5" />
            <p>
              En validant, l'entreprise sera enregistrée et disponible dans la liste complète des
              entreprises.
            </p>
          </div>
        </div>
      )}

      {tab === "docs" && (
        <div className="p-4 text-sm text-slate-500">Documents liés à cette fiche.</div>
      )}
      {tab === "hist" && (
        <div className="p-4 text-sm text-slate-500">Historique des modifications.</div>
      )}
    </aside>
  );
}

// ============================================================================
// COMPOSANTS DU TABLEAU
// ============================================================================

function TypeBadge({ type }: { type: TypeEntite }) {
  const cls =
    type === "Fournisseur" ? "bg-orange-100 text-orange-700" : "bg-emerald-100 text-emerald-700";
  return <span className={`text-[11px] font-medium px-2 py-1 rounded-md ${cls}`}>{type}</span>;
}

function IdRow({ label, value }: { label: string; value: string | null }) {
  return (
    <p className="text-xs text-slate-500">
      {label}: <span className="text-slate-700">{value ?? "Non trouvé"}</span>
    </p>
  );
}

// ============================================================================
// PAGE PRINCIPALE
// Ne contient plus que le contenu propre à la page. Sidebar + Header vivent
// désormais dans Layout.tsx et enveloppent cette page via <Outlet />.
// Nom EXACT attendu par : import { RegistersPage } from "./pages/RegistersPage";
// ============================================================================

export function RegistersPage() {
  const [selectedId, setSelectedId] = useState<string | null>(ROWS[0].id);
  const [checked, setChecked] = useState<Record<string, boolean>>({ "1": true });

  const selectedRow = ROWS.find((r) => r.id === selectedId) ?? null;

  const toggleCheck = (id: string) => setChecked((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Entreprises en attente de validation</h1>
        <p className="text-sm text-slate-500 mt-1">
          Liste des entreprises extraites des documents et en attente de vérification.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={UserRound}
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
          value={24}
          label="En attente"
          caption="À vérifier"
        />
        <StatCard
          icon={UserCog}
          iconBg="bg-orange-100"
          iconColor="text-orange-600"
          value={3}
          label="À compléter"
          caption="Informations manquantes"
        />
        <StatCard
          icon={XCircle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
          value={5}
          label="Rejetées"
          caption="À revoir si besoin"
        />
        <StatCard
          icon={Clock3}
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
          value={0}
          label="Validées ce mois"
          caption="Aucune validation"
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 flex items-center gap-3">
        <div className="flex-1 relative max-w-xs">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher (nom, ICE, IF, RC...)"
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />
        </div>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg px-3 py-2"
        >
          Tous les types <ChevronDown size={14} />
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg px-3 py-2"
        >
          Toutes les sources <ChevronDown size={14} />
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg px-3 py-2"
        >
          Trier par : Plus récent <ChevronDown size={14} />
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg px-3 py-2 ml-auto"
        >
          <SlidersHorizontal size={14} />
          Filtres
        </button>
      </div>

      <div className="flex items-start gap-5">
        <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                  <th className="p-3 w-10">
                    <input type="checkbox" className="rounded border-slate-300" />
                  </th>
                  <th className="p-3">Entreprise</th>
                  <th className="p-3">ICE / IF / RC</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Source</th>
                  <th className="p-3 text-right">Montant TTC</th>
                  <th className="p-3">Extrait le</th>
                  <th className="p-3">Statut</th>
                  <th className="p-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => {
                  const isSelected = row.id === selectedId;
                  const statut = STATUT_STYLES[row.statut];
                  return (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedId(row.id)}
                      className={`border-b border-slate-50 last:border-0 cursor-pointer transition-colors ${
                        isSelected ? "bg-emerald-50/70" : "hover:bg-slate-50"
                      }`}
                    >
                      <td className="p-3" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={!!checked[row.id]}
                          onChange={() => toggleCheck(row.id)}
                          className="rounded border-slate-300"
                        />
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2.5">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${row.avatarColor}`}
                          >
                            {row.initiales}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-800">{row.nom}</p>
                            <p className="text-xs text-slate-400">{row.type}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        <IdRow label="ICE" value={row.ice} />
                        <IdRow label="IF" value={row.ifNumber} />
                        <IdRow label="RC" value={row.rc} />
                      </td>
                      <td className="p-3">
                        <TypeBadge type={row.type} />
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-1.5 text-blue-600">
                          <FileText size={14} />
                          <span className="text-xs">{row.source}</span>
                        </div>
                      </td>
                      <td className="p-3 text-right font-semibold text-slate-800">
                        {money(row.montantTTC)}
                      </td>
                      <td className="p-3 text-xs text-slate-500">
                        <p>{row.extraitLe}</p>
                        <p>{row.extraitA}</p>
                      </td>
                      <td className="p-3">
                        <span
                          className={`text-[11px] font-medium px-2 py-1 rounded-md ${statut.className}`}
                        >
                          {statut.label}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            type="button"
                            onClick={(e) => e.stopPropagation()}
                            className="w-7 h-7 flex items-center justify-center rounded-md bg-blue-50 text-blue-600 hover:bg-blue-100"
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => e.stopPropagation()}
                            className="w-7 h-7 flex items-center justify-center rounded-md bg-red-50 text-red-600 hover:bg-red-100"
                          >
                            <X size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => e.stopPropagation()}
                            className="w-7 h-7 flex items-center justify-center rounded-md text-slate-400 hover:bg-slate-100"
                          >
                            <MoreHorizontal size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
            <p className="text-xs text-slate-500">Affichage 1 à 7 sur 24 résultats</p>
            <div className="flex items-center gap-1.5">
              <button type="button" className="w-7 h-7 flex items-center justify-center rounded-md border border-slate-200 text-slate-400">
                <ChevronLeft size={14} />
              </button>
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`w-7 h-7 flex items-center justify-center rounded-md text-sm ${
                    n === 1
                      ? "bg-emerald-600 text-white font-medium"
                      : "border border-slate-200 text-slate-600"
                  }`}
                >
                  {n}
                </button>
              ))}
              <button type="button" className="w-7 h-7 flex items-center justify-center rounded-md border border-slate-200 text-slate-600">
                <ChevronRight size={14} />
              </button>
              <button
                type="button"
                className="ml-2 flex items-center gap-1 text-xs text-slate-600 border border-slate-200 rounded-md px-2 py-1.5"
              >
                10 / page <ChevronDown size={12} />
              </button>
            </div>
          </div>
        </div>

        {selectedRow && <DetailPanel row={selectedRow} onClose={() => setSelectedId(null)} />}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
        >
          <Download size={15} />
          Exporter la liste
        </button>
        <button
          type="button"
          className="flex items-center gap-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
        >
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>
    </>
  );
}

export default RegistersPage;