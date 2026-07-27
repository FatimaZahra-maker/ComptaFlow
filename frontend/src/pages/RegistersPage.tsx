import { useState, useMemo, useEffect } from "react";
import type { ElementType } from "react";
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
  Check,
} from "lucide-react";

// ============================================================================
// TYPES & DONNÉES DE DÉMO
// TODO(API): remplacer ROWS_INITIAL par un fetch réel, ex:
//   const data = await listEntreprises({ statut, type, source, page, pageSize })
// et brancher les handlers (handleValidate, handleReject, handleDelete,
// handleReprocess, handleSaveEdit) sur les endpoints correspondants au lieu
// de muter l'état local `rows`.
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

const ROWS_INITIAL: EntrepriseRow[] = [
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

function parseRowDate(row: EntrepriseRow): number {
  const [d, m, y] = row.extraitLe.split("/").map(Number);
  const [hh, mm] = row.extraitA.split(":").map(Number);
  return new Date(y, (m || 1) - 1, d, hh, mm).getTime();
}

function escapeCsv(value: string): string {
  if (/[;"\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

// ============================================================================
// DROPDOWN GÉNÉRIQUE (utilisé pour les filtres et le tri)
// ============================================================================

function Dropdown({
  label,
  options,
  selected,
  onSelect,
  align = "left",
}: {
  label?: string;
  options: string[];
  selected: string;
  onSelect: (value: string) => void;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg px-3 py-2 hover:bg-slate-50"
      >
        {label ? `${label} : ${selected}` : selected} <ChevronDown size={14} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className={`absolute z-20 mt-1 w-56 bg-white border border-slate-200 rounded-lg shadow-lg py-1 max-h-64 overflow-y-auto ${
              align === "right" ? "right-0" : "left-0"
            }`}
          >
            {options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => {
                  onSelect(opt);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 flex items-center justify-between ${
                  opt === selected ? "text-emerald-600 font-medium" : "text-slate-700"
                }`}
              >
                {opt}
                {opt === selected && <Check size={14} />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// CARTES DE STATISTIQUES (calculées dynamiquement à partir des lignes)
// ============================================================================

function StatCard({
  icon: Icon,
  iconBg,
  iconColor,
  value,
  label,
  caption,
}: {
  icon: ElementType;
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

function EditableField({
  label,
  value,
  onChange,
  editing,
  required = false,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  editing: boolean;
  required?: boolean;
  multiline?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      {editing ? (
        multiline ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={2}
            className="w-full text-sm text-slate-800 border border-emerald-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full text-sm text-slate-800 border border-emerald-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />
        )
      ) : (
        <div className="w-full text-sm text-slate-800 border border-slate-200 rounded-lg px-3 py-2 bg-white whitespace-pre-line">
          {value || "—"}
        </div>
      )}
    </div>
  );
}

function DetailPanel({
  row,
  onClose,
  onValidate,
  onReject,
  onDelete,
  onReprocess,
  onSaveEdit,
}: {
  row: EntrepriseRow;
  onClose: () => void;
  onValidate: (id: string) => void;
  onReject: (id: string) => void;
  onDelete: (id: string) => void;
  onReprocess: (id: string) => void;
  onSaveEdit: (id: string, patch: Partial<EntrepriseRow>) => void;
}) {
  const [tab, setTab] = useState<"info" | "docs" | "hist">("info");
  const [editing, setEditing] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [draft, setDraft] = useState(row);

  // Resynchronise le brouillon quand on change de fiche sélectionnée
  useEffect(() => {
    setDraft(row);
    setEditing(false);
  }, [row]);

  const statut = STATUT_STYLES[row.statut];

  function handleSave() {
    onSaveEdit(row.id, {
      nom: draft.nom,
      type: draft.type,
      ice: draft.ice,
      ifNumber: draft.ifNumber,
      rc: draft.rc,
      adresse: draft.adresse,
      telephone: draft.telephone,
      email: draft.email,
    });
    setEditing(false);
  }

  function handleCancel() {
    setDraft(row);
    setEditing(false);
  }

  function handleReprocess() {
    setReprocessing(true);
    // TODO(API): remplacer par un vrai appel de retraitement OCR/LLM,
    // ex: await reprocessDocument(row.id)
    setTimeout(() => {
      onReprocess(row.id);
      setReprocessing(false);
    }, 1200);
  }

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
            {!editing ? (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="text-slate-400 hover:text-slate-600"
                title="Modifier les informations"
              >
                <Pencil size={15} />
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  className="text-xs font-medium text-emerald-600 hover:text-emerald-700"
                >
                  Enregistrer
                </button>
              </div>
            )}
          </div>

          <EditableField
            label="Nom de l'entreprise"
            value={draft.nom}
            onChange={(v) => setDraft((d) => ({ ...d, nom: v }))}
            editing={editing}
            required
          />
          <EditableField
            label="Type"
            value={draft.type}
            onChange={(v) => setDraft((d) => ({ ...d, type: v as TypeEntite }))}
            editing={editing}
            required
          />
          <EditableField
            label="ICE"
            value={draft.ice ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, ice: v }))}
            editing={editing}
          />
          <EditableField
            label="IF"
            value={draft.ifNumber ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, ifNumber: v }))}
            editing={editing}
          />
          <EditableField
            label="RC"
            value={draft.rc ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, rc: v }))}
            editing={editing}
          />
          <EditableField
            label="Adresse"
            value={draft.adresse ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, adresse: v }))}
            editing={editing}
            multiline
          />
          <EditableField
            label="Téléphone"
            value={draft.telephone ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, telephone: v }))}
            editing={editing}
          />
          <EditableField
            label="Email"
            value={draft.email ?? ""}
            onChange={(v) => setDraft((d) => ({ ...d, email: v }))}
            editing={editing}
          />
          <EditableField label="Montant TTC" value={money(row.montantTTC)} onChange={() => {}} editing={false} />
          <EditableField label="Source" value={row.source} onChange={() => {}} editing={false} />
          <EditableField
            label="Extrait le"
            value={`${row.extraitLe} à ${row.extraitA}`}
            onChange={() => {}}
            editing={false}
          />

          <div>
            <p className="text-sm font-semibold text-slate-800 mb-3">Actions</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => onValidate(row.id)}
                disabled={row.statut === "valide"}
                className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg py-2.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <CircleCheckBig size={16} />
                Valider
              </button>
              <button
                type="button"
                onClick={() => onReject(row.id)}
                disabled={row.statut === "rejete"}
                className="flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg py-2.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <XCircle size={16} />
                Rejeter
              </button>
              <button
                type="button"
                onClick={handleReprocess}
                disabled={reprocessing}
                className="flex items-center justify-center gap-2 border border-amber-300 text-amber-700 hover:bg-amber-50 text-sm font-medium rounded-lg py-2.5 transition-colors disabled:opacity-50"
              >
                <Sparkles size={16} className={reprocessing ? "animate-spin" : ""} />
                {reprocessing ? "Retraitement…" : "Retraiter avec l'IA"}
              </button>
              <button
                type="button"
                onClick={() => onDelete(row.id)}
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

function RowActionsMenu({
  onViewDetails,
  onDelete,
}: {
  onViewDetails: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="w-7 h-7 flex items-center justify-center rounded-md text-slate-400 hover:bg-slate-100"
      >
        <MoreHorizontal size={15} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1 w-44 bg-white border border-slate-200 rounded-lg shadow-lg py-1">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onViewDetails();
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Voir détails
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50"
            >
              Supprimer
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// PAGE PRINCIPALE
// Nom EXACT attendu par : import { RegistersPage } from "./pages/RegistersPage";
// ============================================================================

const TYPE_OPTIONS = ["Tous les types", "Fournisseur", "Client"];
const SORT_OPTIONS = ["Plus récent", "Plus ancien", "Montant décroissant", "Montant croissant"];
const PAGE_SIZE_OPTIONS = [5, 10, 25, 50];

export function RegistersPage() {
  const [rows, setRows] = useState<EntrepriseRow[]>(ROWS_INITIAL);
  const [selectedId, setSelectedId] = useState<string | null>(ROWS_INITIAL[0]?.id ?? null);
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("Tous les types");
  const [sourceFilter, setSourceFilter] = useState<string>("Toutes les sources");
  const [sortBy, setSortBy] = useState<string>("Plus récent");
  const [showFiltersPanel, setShowFiltersPanel] = useState(false);
  const [statutFilter, setStatutFilter] = useState<Record<Statut, boolean>>({
    a_verifier: true,
    a_completer: true,
    rejete: true,
    valide: true,
  });

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const sourceOptions = useMemo(
    () => ["Toutes les sources", ...Array.from(new Set(rows.map((r) => r.source)))],
    [rows]
  );

  const filteredRows = useMemo(() => {
    let result = [...rows];

    if (searchTerm.trim()) {
      const q = searchTerm.trim().toLowerCase();
      result = result.filter((r) =>
        [r.nom, r.ice, r.ifNumber, r.rc].some((v) => v?.toLowerCase().includes(q))
      );
    }

    if (typeFilter !== "Tous les types") {
      result = result.filter((r) => r.type === typeFilter);
    }

    if (sourceFilter !== "Toutes les sources") {
      result = result.filter((r) => r.source === sourceFilter);
    }

    result = result.filter((r) => statutFilter[r.statut]);

    result.sort((a, b) => {
      if (sortBy === "Plus récent") return parseRowDate(b) - parseRowDate(a);
      if (sortBy === "Plus ancien") return parseRowDate(a) - parseRowDate(b);
      if (sortBy === "Montant décroissant") return b.montantTTC - a.montantTTC;
      if (sortBy === "Montant croissant") return a.montantTTC - b.montantTTC;
      return 0;
    });

    return result;
  }, [rows, searchTerm, typeFilter, sourceFilter, statutFilter, sortBy]);

  // Revenir à la page 1 dès qu'un filtre change, pour éviter une page vide
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, typeFilter, sourceFilter, statutFilter, sortBy, pageSize]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const pagedRows = filteredRows.slice((safePage - 1) * pageSize, safePage * pageSize);

  const selectedRow = rows.find((r) => r.id === selectedId) ?? null;

  const allPagedChecked = pagedRows.length > 0 && pagedRows.every((r) => checked[r.id]);

  function toggleCheck(id: string) {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function toggleCheckAllOnPage() {
    const next = !allPagedChecked;
    setChecked((prev) => {
      const updated = { ...prev };
      pagedRows.forEach((r) => {
        updated[r.id] = next;
      });
      return updated;
    });
  }

  function handleUpdateStatut(id: string, statut: Statut) {
    // TODO(API): remplacer par validateEntry(id) / rejectEntry(id) puis refresh()
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, statut } : r)));
  }

  function handleDelete(id: string) {
    const row = rows.find((r) => r.id === id);
    if (!row) return;
    const confirmed = window.confirm(`Supprimer définitivement "${row.nom}" ?`);
    if (!confirmed) return;
    // TODO(API): remplacer par un appel deleteEntreprise(id) puis refresh()
    setRows((prev) => prev.filter((r) => r.id !== id));
    setChecked((prev) => {
      const { [id]: _removed, ...rest } = prev;
      return rest;
    });
    if (selectedId === id) setSelectedId(null);
  }

  function handleReprocess(id: string) {
    // TODO(API): déclencher le vrai pipeline OCR/LLM (Ollama → Groq → Gemini → regex)
    // puis remplacer les champs extraits une fois le résultat reçu.
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, statut: "a_verifier" } : r)));
  }

  function handleSaveEdit(id: string, patch: Partial<EntrepriseRow>) {
    // TODO(API): remplacer par un PATCH /entreprises/{id}
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function handleRefresh() {
    setIsRefreshing(true);
    // TODO(API): remplacer par un vrai refetch, ex: await listEntreprises(...)
    setSearchTerm("");
    setTypeFilter("Tous les types");
    setSourceFilter("Toutes les sources");
    setSortBy("Plus récent");
    setStatutFilter({ a_verifier: true, a_completer: true, rejete: true, valide: true });
    setTimeout(() => setIsRefreshing(false), 600);
  }

  function handleExport() {
    const headers = ["Nom", "Type", "ICE", "IF", "RC", "Source", "Montant TTC", "Extrait le", "Statut"];
    const csvRows = filteredRows.map((r) => [
      r.nom,
      r.type,
      r.ice ?? "",
      r.ifNumber ?? "",
      r.rc ?? "",
      r.source,
      r.montantTTC.toFixed(2),
      `${r.extraitLe} ${r.extraitA}`,
      STATUT_STYLES[r.statut].label,
    ]);
    const csvContent = [headers, ...csvRows]
      .map((line) => line.map((cell) => escapeCsv(String(cell))).join(";"))
      .join("\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `entreprises_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  const countByStatut = (s: Statut) => rows.filter((r) => r.statut === s).length;

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
          value={countByStatut("a_verifier")}
          label="En attente"
          caption="À vérifier"
        />
        <StatCard
          icon={UserCog}
          iconBg="bg-orange-100"
          iconColor="text-orange-600"
          value={countByStatut("a_completer")}
          label="À compléter"
          caption="Informations manquantes"
        />
        <StatCard
          icon={XCircle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
          value={countByStatut("rejete")}
          label="Rejetées"
          caption="À revoir si besoin"
        />
        <StatCard
          icon={Clock3}
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
          value={countByStatut("valide")}
          label="Validées ce mois"
          caption={countByStatut("valide") === 0 ? "Aucune validation" : "Mis à jour"}
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex-1 relative max-w-xs">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Rechercher (nom, ICE, IF, RC...)"
              className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            />
          </div>

          <Dropdown options={TYPE_OPTIONS} selected={typeFilter} onSelect={setTypeFilter} />
          <Dropdown options={sourceOptions} selected={sourceFilter} onSelect={setSourceFilter} />
          <Dropdown label="Trier par" options={SORT_OPTIONS} selected={sortBy} onSelect={setSortBy} />

          <button
            type="button"
            onClick={() => setShowFiltersPanel((v) => !v)}
            className={`flex items-center gap-1.5 text-sm font-medium border rounded-lg px-3 py-2 ml-auto ${
              showFiltersPanel
                ? "border-emerald-300 text-emerald-700 bg-emerald-50"
                : "border-slate-200 text-slate-700"
            }`}
          >
            <SlidersHorizontal size={14} />
            Filtres
          </button>
        </div>

        {showFiltersPanel && (
          <div className="flex items-center gap-4 flex-wrap border-t border-slate-100 pt-3">
            <span className="text-xs font-medium text-slate-500">Statut :</span>
            {(Object.keys(STATUT_STYLES) as Statut[]).map((s) => (
              <label key={s} className="flex items-center gap-1.5 text-sm text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={statutFilter[s]}
                  onChange={() =>
                    setStatutFilter((prev) => ({ ...prev, [s]: !prev[s] }))
                  }
                  className="rounded border-slate-300"
                />
                {STATUT_STYLES[s].label}
              </label>
            ))}
            <button
              type="button"
              onClick={() =>
                setStatutFilter({ a_verifier: true, a_completer: true, rejete: true, valide: true })
              }
              className="text-xs font-medium text-slate-400 hover:text-slate-600 ml-auto"
            >
              Réinitialiser
            </button>
          </div>
        )}
      </div>

      <div className="flex items-start gap-5">
        <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                  <th className="p-3 w-10">
                    <input
                      type="checkbox"
                      checked={allPagedChecked}
                      onChange={toggleCheckAllOnPage}
                      className="rounded border-slate-300"
                    />
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
                {pagedRows.map((row) => {
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
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedId(row.id);
                            }}
                            title="Modifier"
                            className="w-7 h-7 flex items-center justify-center rounded-md bg-blue-50 text-blue-600 hover:bg-blue-100"
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleUpdateStatut(row.id, "rejete");
                            }}
                            title="Rejeter rapidement"
                            disabled={row.statut === "rejete"}
                            className="w-7 h-7 flex items-center justify-center rounded-md bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-40"
                          >
                            <X size={14} />
                          </button>
                          <RowActionsMenu
                            onViewDetails={() => setSelectedId(row.id)}
                            onDelete={() => handleDelete(row.id)}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {pagedRows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-sm text-slate-400">
                      Aucune entreprise ne correspond à ces filtres.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
            <p className="text-xs text-slate-500">
              {filteredRows.length === 0
                ? "Aucun résultat"
                : `Affichage ${(safePage - 1) * pageSize + 1} à ${Math.min(
                    safePage * pageSize,
                    filteredRows.length
                  )} sur ${filteredRows.length} résultats`}
            </p>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
                className="w-7 h-7 flex items-center justify-center rounded-md border border-slate-200 text-slate-400 disabled:opacity-40 enabled:hover:bg-slate-50 enabled:text-slate-600"
              >
                <ChevronLeft size={14} />
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCurrentPage(n)}
                  className={`w-7 h-7 flex items-center justify-center rounded-md text-sm ${
                    n === safePage
                      ? "bg-emerald-600 text-white font-medium"
                      : "border border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {n}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage === totalPages}
                className="w-7 h-7 flex items-center justify-center rounded-md border border-slate-200 text-slate-600 disabled:opacity-40 enabled:hover:bg-slate-50"
              >
                <ChevronRight size={14} />
              </button>
              <div className="ml-2">
                <Dropdown
                  options={PAGE_SIZE_OPTIONS.map((n) => `${n} / page`)}
                  selected={`${pageSize} / page`}
                  onSelect={(v) => setPageSize(Number(v.split(" ")[0]))}
                  align="right"
                />
              </div>
            </div>
          </div>
        </div>

        {selectedRow && (
          <DetailPanel
            row={selectedRow}
            onClose={() => setSelectedId(null)}
            onValidate={(id) => handleUpdateStatut(id, "valide")}
            onReject={(id) => handleUpdateStatut(id, "rejete")}
            onDelete={handleDelete}
            onReprocess={handleReprocess}
            onSaveEdit={handleSaveEdit}
          />
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleExport}
          className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors"
        >
          <Download size={15} />
          Exporter la liste
        </button>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-lg px-4 py-2.5 transition-colors disabled:opacity-60"
        >
          <RefreshCw size={15} className={isRefreshing ? "animate-spin" : ""} />
          Actualiser
        </button>
      </div>
    </>
  );
}

export default RegistersPage;