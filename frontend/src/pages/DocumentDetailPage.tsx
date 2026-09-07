import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ExternalLink,
  FileImage,
  FileSpreadsheet,
  FileText,
  Pencil,
  RefreshCw,
  Save,
  Trash2,
  X,
  XCircle,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { updateEntry } from "../api/accountingApi";
import { getDocumentDetail } from "../api/documentDetailApi";
import {
  assignDocumentEntreprise,
  deleteDocument,
  downloadDocumentData,
  fetchDocumentFile,
  rejectDocument,
  retraiterDocument,
  toggleDocumentSaisie,
  updateBankMovement,
  validateDocument,
} from "../api/documentsApi";
import { listEntreprises } from "../api/entreprisesApi";
import { listPlanAccounts } from "../api/planComptableApi";
import { useAuth } from "../context/AuthContext";

import type { DocumentDetail, EcritureResume } from "../types/documentDetail";
import type { Entreprise } from "../types/entreprise";
import type { CompteComptableEntreprise } from "../types/planComptable";
import type {
  MouvementBancaire,
  MouvementBancaireUpdate,
  TypeMouvementBancaire,
} from "../types/mouvementBancaire";

const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  en_attente: "En attente",
  en_traitement: "En traitement",
  traite: "Traité",
  valide: "Validé",
  erreur: "Erreur",
};

const DOCUMENT_STATUS_CLASSES: Record<string, string> = {
  en_attente: "bg-slate-100 text-slate-700",
  en_traitement: "bg-amber-100 text-amber-700",
  traite: "bg-blue-100 text-blue-700",
  valide: "bg-emerald-100 text-emerald-700",
  erreur: "bg-red-100 text-red-700",
};

const VALIDATION_LABELS: Record<string, string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validé",
  rejete: "Rejeté",
};

const VALIDATION_CLASSES: Record<string, string> = {
  brouillon: "bg-slate-100 text-slate-700",
  a_verifier: "bg-orange-100 text-orange-700",
  valide: "bg-emerald-100 text-emerald-700",
  rejete: "bg-red-100 text-red-700",
};

const EXTRACTED_FIELD_LABELS: Record<string, string> = {
  categorie: "Catégorie",
  type_document: "Type de document",
  numero_piece: "N° pièce / facture",
  numero_facture: "N° facture",
  date_piece: "Date de la pièce",
  date: "Date",
  tiers: "Tiers",
  nom_fournisseur: "Fournisseur",
  nom_client: "Client",
  ice_fournisseur: "ICE fournisseur",
  ice_client: "ICE client",
  if_fournisseur: "IF fournisseur",
  if_client: "IF client",
  rc_fournisseur: "RC fournisseur",
  rc_client: "RC client",
  montant_ht: "Montant HT",
  ht: "Montant HT",
  taux_tva: "Taux TVA",
  montant_tva: "Montant TVA",
  tva: "Montant TVA",
  montant_ttc: "Montant TTC",
  ttc: "Montant TTC",
  source_extraction: "Source d'extraction",
  a_verifier: "À vérifier",
  raison_verification: "Raison de vérification",
};

const INPUT_CLASS =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10";

interface EntryFormState {
  tiers: string;
  numero_piece: string;
  date_piece: string;
  montant_ht: string;
  taux_tva: string;
  montant_tva: string;
  montant_ttc: string;
  compte_tiers: string;
  compte_tva: string;
  compte_ht: string;
}

interface MovementFormState {
  id: string;
  date_operation: string;
  libelle: string;
  reference: string;
  type_mouvement: TypeMouvementBancaire;
  montant: string;
  solde_apres_operation: string;
}

interface ExtractedRow {
  key: string;
  label: string;
  value: string;
}

function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const amount = typeof value === "number" ? value : Number.parseFloat(value);

  if (Number.isNaN(amount)) {
    return "—";
  }

  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + " MAD";
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("fr-FR");
}

function formatExtractedValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "Oui" : "Non";
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function humanizeFieldName(key: string): string {
  return (
    EXTRACTED_FIELD_LABELS[key] ??
    key
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function normalizeMovementType(value: string): TypeMouvementBancaire {
  return value.toLowerCase() === "credit" ? "credit" : "debit";
}

function createEntryForm(entry: EcritureResume): EntryFormState {
  return {
    tiers: entry.tiers ?? "",
    numero_piece: entry.numero_piece ?? "",
    date_piece: entry.date_piece ?? "",
    montant_ht: entry.montant_ht ?? "",
    taux_tva: entry.taux_tva ?? "",
    montant_tva: entry.montant_tva ?? "",
    montant_ttc: entry.montant_ttc ?? "",
    compte_tiers: entry.compte_tiers ?? "",
    compte_tva: entry.compte_tva ?? "",
    compte_ht: entry.compte_ht ?? "",
  };
}

function requestErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;
  const detail = error.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter((item): item is string => typeof item === "string");
    if (messages.length) return messages.join(" | ");
  }
  if (!error.response) return "Le backend est inaccessible. Vérifiez qu’il est démarré.";
  return fallback;
}

function createMovementForm(movement: MouvementBancaire): MovementFormState {
  return {
    id: movement.id,
    date_operation: movement.date_operation,
    libelle: movement.libelle,
    reference: movement.reference ?? "",
    type_mouvement: normalizeMovementType(movement.type_mouvement),
    montant: String(movement.montant ?? ""),
    solde_apres_operation:
      movement.solde_apres_operation === null ||
      movement.solde_apres_operation === undefined
        ? ""
        : String(movement.solde_apres_operation),
  };
}

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <span className="mb-1 block text-xs font-semibold text-slate-600">
      {children}
    </span>
  );
}

function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={INPUT_CLASS} />;
}

function DataCard({
  label,
  value,
  important = false,
}: {
  label: string;
  value: string;
  important?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p
        className={`mt-1 break-words text-slate-900 ${
          important ? "text-lg font-bold" : "text-sm font-semibold"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [planAccounts, setPlanAccounts] = useState<CompteComptableEntreprise[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [isEntryModalOpen, setIsEntryModalOpen] = useState(false);
  const [movementForm, setMovementForm] = useState<MovementFormState | null>(null);
  const [entryForm, setEntryForm] = useState<EntryFormState>({
    tiers: "",
    numero_piece: "",
    date_piece: "",
    montant_ht: "",
    taux_tva: "",
    montant_tva: "",
    montant_ttc: "",
    compte_tiers: "",
    compte_tva: "",
    compte_ht: "",
  });

  const canReview = Boolean(user && ["admin_cabinet", "expert_comptable", "chef_mission"].includes(user.role));

  const refresh = useCallback(async () => {
    if (!id) {
      setError("Identifiant du document manquant.");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await getDocumentDetail(id);
      setDetail(data);
    } catch {
      setDetail(null);
      setError("Impossible de charger ce document.");
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const documentFileId = detail?.id;

  useEffect(() => {
    if (!documentFileId) return;
    let active = true;
    let objectUrl: string | null = null;
    fetchDocumentFile(documentFileId)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setFileUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFileUrl(null);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setFileUrl(null);
    };
  }, [documentFileId]);

  useEffect(() => {
    let mounted = true;

    listEntreprises()
      .then((data) => {
        if (mounted) {
          setEntreprises(data);
        }
      })
      .catch(() => undefined);

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!detail?.entreprise_id) {
      setPlanAccounts([]);
      return;
    }
    listPlanAccounts(detail.entreprise_id)
      .then(setPlanAccounts)
      .catch(() => setPlanAccounts([]));
  }, [detail?.entreprise_id]);

  const entrepriseName = useMemo(() => {
    if (!detail?.entreprise_id) {
      return "Entreprise à identifier";
    }

    return (
      entreprises.find((item) => item.id === detail.entreprise_id)?.nom ??
      "Entreprise inconnue"
    );
  }, [detail?.entreprise_id, entreprises]);

  const extractedRows = useMemo<ExtractedRow[]>(() => {
    if (!detail?.donnees_extraites) {
      return [];
    }

    return Object.entries(detail.donnees_extraites)
      .filter(([key]) => key !== "lignes_bancaires" && !key.startsWith("_"))
      .map(([key, value]) => ({
        key,
        label: humanizeFieldName(key),
        value: formatExtractedValue(value),
      }));
  }, [detail?.donnees_extraites]);

  const movements = detail?.mouvements_bancaires ?? [];
  const isBankDocument = detail?.categorie === "banque" || movements.length > 0;

  function showSuccess(message: string) {
    setError(null);
    setSuccess(message);
  }

  function showError(message: string) {
    setSuccess(null);
    setError(message);
  }

  function openEntryEditor() {
    if (!detail?.ecriture) {
      return;
    }

    setEntryForm(createEntryForm(detail.ecriture));
    setIsEntryModalOpen(true);
  }

  function openMovementEditor(movement: MouvementBancaire) {
    setMovementForm(createMovementForm(movement));
  }

  async function saveEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!detail?.ecriture) {
      return;
    }

    setCurrentAction("save-entry");

    try {
      await updateEntry(detail.ecriture.id, {
        tiers: entryForm.tiers.trim(),
        numero_piece: entryForm.numero_piece.trim(),
        date_piece: entryForm.date_piece || undefined,
        montant_ht: entryForm.montant_ht || undefined,
        taux_tva: entryForm.taux_tva || undefined,
        montant_tva: entryForm.montant_tva || undefined,
        montant_ttc: entryForm.montant_ttc || undefined,
        compte_tiers: entryForm.compte_tiers || null,
        compte_tva: entryForm.compte_tva || null,
        compte_ht: entryForm.compte_ht || null,
      });

      setIsEntryModalOpen(false);
      await refresh();
      showSuccess("Les données comptables ont été modifiées.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "La modification des données comptables a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function saveMovement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!detail || !movementForm) {
      return;
    }

    const payload: MouvementBancaireUpdate = {
      date_operation: movementForm.date_operation,
      libelle: movementForm.libelle.trim(),
      reference: movementForm.reference.trim() || null,
      type_mouvement: movementForm.type_mouvement,
      montant: movementForm.montant,
      solde_apres_operation:
        movementForm.solde_apres_operation === ""
          ? null
          : movementForm.solde_apres_operation,
    };

    setCurrentAction("save-movement");

    try {
      await updateBankMovement(detail.id, movementForm.id, payload);
      setMovementForm(null);
      await refresh();
      showSuccess("Le mouvement bancaire a été modifié.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "La modification du mouvement bancaire a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleValidate() {
    if (!detail) {
      return;
    }

    setCurrentAction("validate");

    try {
      const updated = await validateDocument(detail.id);
      setDetail(updated);
      showSuccess("Le document a été validé.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "La validation du document a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleAssignEntreprise(entrepriseId: string) {
    if (!detail || !entrepriseId || entrepriseId === detail.entreprise_id) return;
    setCurrentAction("assign-company");
    try {
      const updated = await assignDocumentEntreprise(detail.id, entrepriseId);
      setDetail(updated);
      showSuccess("Entreprise attribuée. Le retraitement sécurisé du document a été lancé.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "L’attribution de l’entreprise a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleReject() {
    if (!detail) {
      return;
    }

    const confirmed = window.confirm(
      "Rejeter ce document ? Il restera disponible pour correction.",
    );

    if (!confirmed) {
      return;
    }

    setCurrentAction("reject");

    try {
      const updated = await rejectDocument(detail.id);
      setDetail(updated);
      showSuccess("Le document a été rejeté.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "Le rejet du document a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleToggleSaisie() {
    if (!detail) {
      return;
    }

    setCurrentAction("saisie");

    try {
      const result = await toggleDocumentSaisie(detail.id);
      setDetail((current) =>
        current
          ? {
              ...current,
              saisie_topaze: result.saisie_topaze,
            }
          : current,
      );

      showSuccess(
        result.saisie_topaze
          ? "Le document est maintenant marqué comme saisi."
          : "Le document n'est plus marqué comme saisi.",
      );
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "La mise à jour du statut de saisie a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleRetraiter() {
    if (!detail) {
      return;
    }

    const confirmed = window.confirm(
      "Relancer l'OCR et l'extraction ?\n\nLes données extraites actuelles seront remplacées.",
    );

    if (!confirmed) {
      return;
    }

    setCurrentAction("retraiter");

    try {
      await retraiterDocument(detail.id);
      await refresh();
      showSuccess("Le retraitement du document a été lancé.");
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "Le retraitement du document a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleDelete() {
    if (!detail) {
      return;
    }

    const confirmed = window.confirm(
      `Supprimer définitivement « ${detail.nom_fichier_original} » ?\n\n` +
        "Le fichier, les données extraites, l'écriture comptable et les mouvements bancaires seront supprimés. " +
        "Vous pourrez ensuite réimporter le même fichier.",
    );

    if (!confirmed) {
      return;
    }

    setCurrentAction("delete");

    try {
      await deleteDocument(detail.id);
      navigate("/chronos", { replace: true });
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "La suppression définitive du document a échoué."));
      setCurrentAction(null);
    }
  }

  async function handleExport(format: "csv" | "xlsx") {
    if (!detail) {
      return;
    }

    setCurrentAction(`export-${format}`);

    try {
      await downloadDocumentData(detail.id, format, detail.nom_fichier_original);
      showSuccess(
        `Les données extraites ont été exportées en ${
          format === "xlsx" ? "Excel" : "CSV"
        }.`,
      );
    } catch (requestError) {
      showError(requestErrorMessage(requestError, "L'export des données extraites a échoué."));
    } finally {
      setCurrentAction(null);
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[55vh] items-center justify-center text-slate-500">
        <RefreshCw className="mr-2 animate-spin" size={20} />
        Chargement du document…
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-6">
        <div className="max-w-xl rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">
          <p className="font-semibold">{error ?? "Document introuvable."}</p>
          <button
            type="button"
            onClick={() => navigate("/chronos")}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold shadow-sm"
          >
            <ArrowLeft size={16} />
            Retour au Chronos
          </button>
        </div>
      </div>
    );
  }

  const isImage = detail.mime_type?.startsWith("image/") ?? false;
  const isPdf = detail.mime_type === "application/pdf";
  const validationStatus =
    detail.ecriture?.statut_validation ??
    (detail.statut === "valide" ? "valide" : "a_verifier");
  const entryType = detail.ecriture?.type_ecriture;
  const thirdPartyUsage = entryType === "vente" ? "client" : "fournisseur";
  const thirdPartyAccounts = planAccounts.filter((account) => account.type_usage === thirdPartyUsage);
  const htAccounts = planAccounts.filter((account) => account.type_usage === "ht");
  const vatAccounts = planAccounts.filter((account) => account.type_usage === "tva");

  return (
    <div className="min-h-screen bg-slate-50 p-4 lg:p-6">
      <div className="mx-auto max-w-[1800px]">
        <header className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <button
                type="button"
                onClick={() => navigate("/chronos")}
                className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-blue-700"
              >
                <ArrowLeft size={15} />
                Retour au Chronos
              </button>

              <div className="flex flex-wrap items-center gap-2">
                <h1
                  className="max-w-3xl truncate text-xl font-bold text-slate-900"
                  title={detail.nom_fichier_original}
                >
                  {detail.nom_fichier_original}
                </h1>

                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    DOCUMENT_STATUS_CLASSES[detail.statut] ??
                    "bg-slate-100 text-slate-700"
                  }`}
                >
                  {DOCUMENT_STATUS_LABELS[detail.statut] ?? detail.statut}
                </span>

                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    VALIDATION_CLASSES[validationStatus] ??
                    "bg-slate-100 text-slate-700"
                  }`}
                >
                  {VALIDATION_LABELS[validationStatus] ?? validationStatus}
                </span>
              </div>

              <p className="mt-1.5 text-sm text-slate-500">
                {entrepriseName}
                {detail.categorie ? ` • ${detail.categorie}` : ""}
                {detail.annee ? ` • ${detail.annee}` : ""}
                {detail.mois
                  ? `/${String(detail.mois).padStart(2, "0")}`
                  : ""}
              </p>
              <label className="mt-3 flex max-w-xl items-center gap-2 text-xs font-bold text-slate-600">
                Attribuer à
                <select
                  value={entreprises.some((item) => item.id === detail.entreprise_id && !item.creee_automatiquement) ? detail.entreprise_id ?? "" : ""}
                  onChange={(event) => void handleAssignEntreprise(event.target.value)}
                  disabled={currentAction === "assign-company"}
                  className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium outline-none focus:border-blue-500"
                >
                  <option value="">Choisir une entreprise confirmée…</option>
                  {entreprises.filter((item) => item.is_active !== false && !item.creee_automatiquement).map((item) => <option key={item.id} value={item.id}>{item.nom}</option>)}
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => void handleExport("csv")}
                disabled={currentAction === "export-csv"}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <FileText size={16} />
                CSV
              </button>

              <button
                type="button"
                onClick={() => void handleExport("xlsx")}
                disabled={currentAction === "export-xlsx"}
                className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
              >
                <FileSpreadsheet size={16} />
                Excel
              </button>

              <a
                href={fileUrl ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink size={16} />
                Fichier
              </a>

              <button
                type="button"
                onClick={() => void handleRetraiter()}
                disabled={currentAction === "retraiter"}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
              >
                <RefreshCw
                  size={16}
                  className={currentAction === "retraiter" ? "animate-spin" : ""}
                />
                Retraiter
              </button>

              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={currentAction === "delete"}
                className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
              >
                <Trash2 size={16} />
                Supprimer
              </button>
            </div>
          </div>
        </header>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <XCircle className="mt-0.5 shrink-0" size={17} />
            {error}
          </div>
        )}

        {success && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            <CheckCircle2 className="mt-0.5 shrink-0" size={17} />
            {success}
          </div>
        )}

        {detail.ecriture && ["a_verifier", "brouillon", "rejete"].includes(validationStatus) && (
          <section className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 shrink-0 text-amber-600" size={20} />
                <div>
                  <p className="font-bold text-amber-950">Ce document nécessite votre contrôle</p>
                  <p className="mt-1 text-sm text-amber-800">Comparez la pièce originale aux données extraites, corrigez-les si nécessaire, puis validez le document.</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 lg:shrink-0">
                <button type="button" onClick={openEntryEditor} disabled={!canReview} title={!canReview ? "Action réservée aux responsables de validation." : undefined} className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"><Pencil size={16} />Modifier les données</button>
                <button type="button" onClick={() => void handleReject()} disabled={!canReview || currentAction === "reject"} title={!canReview ? "Action réservée aux responsables de validation." : undefined} className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"><X size={16} />Rejeter</button>
                <button type="button" onClick={() => void handleValidate()} disabled={!canReview || currentAction === "validate"} title={!canReview ? "Action réservée aux responsables de validation." : undefined} className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"><Check size={16} />Valider</button>
              </div>
            </div>
            {!canReview && <p className="mt-3 text-xs font-semibold text-amber-800">Votre rôle permet la consultation, mais la modification, le rejet et la validation sont réservés à l’administrateur, à l’expert-comptable ou au chef de mission.</p>}
          </section>
        )}

        {detail.message_erreur && (
          <div className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle className="mt-0.5 shrink-0" size={17} />
            <div>
              <p className="font-semibold">Erreur de traitement</p>
              <p>{detail.message_erreur}</p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5">
              <div className="flex items-center gap-2.5">
                <FileImage size={19} className="text-blue-700" />
                <div>
                  <h2 className="text-sm font-bold text-slate-900">
                    Document original
                  </h2>
                  <p className="text-xs text-slate-500">
                    Comparez le document aux données extraites.
                  </p>
                </div>
              </div>

              {isImage && (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setZoom((value) => Math.max(50, value - 10))}
                    className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
                    title="Réduire"
                  >
                    <ZoomOut size={17} />
                  </button>
                  <span className="min-w-12 text-center text-xs font-semibold text-slate-500">
                    {zoom}%
                  </span>
                  <button
                    type="button"
                    onClick={() => setZoom((value) => Math.min(200, value + 10))}
                    className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
                    title="Agrandir"
                  >
                    <ZoomIn size={17} />
                  </button>
                </div>
              )}
            </div>

            <div className="h-[720px] overflow-auto bg-slate-100 p-3">
              {isPdf && fileUrl && (
                <iframe
                  src={fileUrl}
                  title={`Aperçu de ${detail.nom_fichier_original}`}
                  className="h-full w-full rounded-xl border-0 bg-white"
                />
              )}

              {isImage && fileUrl && (
                <div className="flex min-h-full items-start justify-center">
                  <img
                    src={fileUrl}
                    alt={detail.nom_fichier_original}
                    style={{ width: `${zoom}%` }}
                    className="max-w-none rounded-xl bg-white shadow"
                  />
                </div>
              )}

              {!isPdf && !isImage && (
                <div className="flex h-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-white text-center text-slate-500">
                  <FileText size={44} className="mb-3 text-slate-300" />
                  <p className="font-semibold">Aperçu non disponible</p>
                  <p className="mt-1 text-xs">
                    Utilisez le bouton « Fichier » pour l'ouvrir.
                  </p>
                </div>
              )}
            </div>
          </section>

          <section className="space-y-5">
            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
                <div>
                  <h2 className="font-bold text-slate-900">
                    Données comptables extraites
                  </h2>
                  <p className="text-xs text-slate-500">
                    Vérifiez puis corrigez les informations.
                  </p>
                </div>

                {detail.ecriture && (
                  <button
                    type="button"
                    onClick={openEntryEditor}
                    className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
                  >
                    <Pencil size={15} />
                    Modifier
                  </button>
                )}
              </div>

              {detail.ecriture ? (
                <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
                  <DataCard
                    label="N° facture"
                    value={detail.ecriture.numero_piece ?? "—"}
                  />
                  <DataCard
                    label="Date"
                    value={formatDate(detail.ecriture.date_piece)}
                  />
                  <DataCard
                    label="Tiers"
                    value={detail.ecriture.tiers ?? "—"}
                  />
                  <DataCard
                    label="Type"
                    value={detail.ecriture.type_ecriture}
                  />
                  <DataCard
                    label="Montant HT"
                    value={formatMoney(detail.ecriture.montant_ht)}
                  />
                  <DataCard
                    label="TVA"
                    value={`${formatMoney(detail.ecriture.montant_tva)}${
                      detail.ecriture.taux_tva
                        ? ` (${detail.ecriture.taux_tva} %)`
                        : ""
                    }`}
                  />
                  <DataCard
                    label="Montant TTC"
                    value={formatMoney(detail.ecriture.montant_ttc)}
                    important
                  />
                  <DataCard
                    label="Validation"
                    value={
                      VALIDATION_LABELS[detail.ecriture.statut_validation] ??
                      detail.ecriture.statut_validation
                    }
                  />
                </div>
              ) : (
                <div className="px-5 py-6 text-sm text-slate-500">
                  {isBankDocument
                    ? "Ce relevé utilise les mouvements bancaires affichés ci-dessous."
                    : "Aucune écriture comptable n'a encore été créée."}
                </div>
              )}

              {detail.ecriture?.anomalie_detectee && (
                <div className="m-4 flex gap-2 rounded-xl border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
                  <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                  <div>
                    <p className="font-semibold">Anomalie détectée</p>
                    <p>
                      {detail.ecriture.anomalie_details ??
                        "Une vérification manuelle est nécessaire."}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="font-bold text-slate-900">
                  Données détectées par l'OCR / IA
                </h2>
                <p className="text-xs text-slate-500">
                  Ces valeurs sont incluses dans les exports CSV et Excel.
                </p>
              </div>

              <div className="max-h-[390px] overflow-auto">
                {extractedRows.length === 0 ? (
                  <p className="px-5 py-6 text-sm text-slate-400">
                    Aucune donnée structurée n'a été extraite.
                  </p>
                ) : (
                  <table className="w-full text-sm">
                    <tbody>
                      {extractedRows.map((row) => (
                        <tr
                          key={row.key}
                          className="border-b border-slate-100 last:border-0"
                        >
                          <th className="w-2/5 bg-slate-50/80 px-4 py-3 text-left align-top text-xs font-semibold text-slate-500">
                            {row.label}
                          </th>
                          <td className="whitespace-pre-wrap break-words px-4 py-3 text-slate-800">
                            {row.value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </section>
        </div>

        {isBankDocument && (
          <section className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="font-bold text-slate-900">
                Mouvements bancaires extraits
              </h2>
              <p className="text-xs text-slate-500">
                Corrigez chaque mouvement avant la validation du relevé.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[950px] text-sm">
                <thead>
                  <tr className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Libellé</th>
                    <th className="px-4 py-3">Référence</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3 text-right">Montant</th>
                    <th className="px-4 py-3 text-right">Solde</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((movement) => {
                    const movementType = normalizeMovementType(
                      movement.type_mouvement,
                    );

                    return (
                      <tr
                        key={movement.id}
                        className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                      >
                        <td className="px-4 py-3">
                          {formatDate(movement.date_operation)}
                        </td>
                        <td className="max-w-lg px-4 py-3">
                          {movement.libelle}
                        </td>
                        <td className="px-4 py-3 text-slate-500">
                          {movement.reference ?? "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-1 text-xs font-semibold ${
                              movementType === "credit"
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {movementType === "credit" ? "Crédit" : "Débit"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-semibold">
                          {formatMoney(movement.montant)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {formatMoney(movement.solde_apres_operation)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => openMovementEditor(movement)}
                            className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                          >
                            <Pencil size={14} />
                            Modifier
                          </button>
                        </td>
                      </tr>
                    );
                  })}

                  {movements.length === 0 && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-8 text-center text-slate-400"
                      >
                        Aucun mouvement bancaire n'a été extrait.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <section className="sticky bottom-4 z-20 mt-5 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="inline-flex cursor-pointer items-center gap-3 rounded-xl border border-slate-200 px-4 py-2.5 hover:bg-slate-50">
              <input
                type="checkbox"
                checked={Boolean(detail.saisie_topaze)}
                disabled={currentAction === "saisie"}
                onChange={() => void handleToggleSaisie()}
                className="h-4 w-4 accent-blue-600"
              />
              <span className="text-sm font-semibold text-slate-700">
                {isBankDocument
                  ? "Relevé bancaire saisi"
                  : "Facture saisie dans Topaze"}
              </span>
            </label>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleReject()}
                disabled={!canReview || currentAction === "reject"}
                title={!canReview ? "Action réservée aux responsables de validation." : undefined}
                className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-5 py-2.5 text-sm font-bold text-red-700 hover:bg-red-100 disabled:opacity-50"
              >
                <X size={17} />
                Rejeter
              </button>

              <button
                type="button"
                onClick={() => void handleValidate()}
                disabled={!canReview || currentAction === "validate"}
                title={!canReview ? "Action réservée aux responsables de validation." : undefined}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-6 py-2.5 text-sm font-bold text-white hover:bg-blue-800 disabled:opacity-50"
              >
                <Check size={17} />
                Valider le document
              </button>
            </div>
          </div>
        </section>
      </div>

      {isEntryModalOpen && detail.ecriture && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <form
            onSubmit={(event) => void saveEntry(event)}
            className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Modifier les données comptables
                </h2>
                <p className="text-xs text-slate-500">
                  Comparez les valeurs avec le document original.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsEntryModalOpen(false)}
                className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
              >
                <X size={19} />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="sm:col-span-2">
                <FieldLabel>Tiers / Fournisseur / Client</FieldLabel>
                <TextInput
                  value={entryForm.tiers}
                  onChange={(event) =>
                    setEntryForm({ ...entryForm, tiers: event.target.value })
                  }
                />
              </label>

              <label>
                <FieldLabel>N° pièce / facture</FieldLabel>
                <TextInput
                  value={entryForm.numero_piece}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      numero_piece: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Date de la pièce</FieldLabel>
                <TextInput
                  type="date"
                  value={entryForm.date_piece}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      date_piece: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Montant HT</FieldLabel>
                <TextInput
                  type="number"
                  step="0.01"
                  value={entryForm.montant_ht}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      montant_ht: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Taux TVA</FieldLabel>
                <select
                  value={entryForm.taux_tva}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      taux_tva: event.target.value,
                    })
                  }
                  className={INPUT_CLASS}
                >
                  <option value="">Non défini</option>
                  <option value="20">20 %</option>
                  <option value="14">14 %</option>
                  <option value="10">10 %</option>
                  <option value="7">7 %</option>
                  <option value="0">0 %</option>
                </select>
              </label>

              <label>
                <FieldLabel>Montant TVA</FieldLabel>
                <TextInput
                  type="number"
                  step="0.01"
                  value={entryForm.montant_tva}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      montant_tva: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Montant TTC</FieldLabel>
                <TextInput
                  type="number"
                  step="0.01"
                  required
                  value={entryForm.montant_ttc}
                  onChange={(event) =>
                    setEntryForm({
                      ...entryForm,
                      montant_ttc: event.target.value,
                    })
                  }
                />
              </label>

              <div className="sm:col-span-2 mt-2 border-t border-slate-100 pt-4">
                <p className="text-sm font-bold text-slate-900">Imputation comptable</p>
                <p className="mt-1 text-xs text-slate-500">Seuls les comptes actifs du plan comptable de cette entreprise peuvent être sélectionnés.</p>
              </div>

              <label>
                <FieldLabel>Compte {thirdPartyUsage === "client" ? "client" : "fournisseur"}</FieldLabel>
                <select value={entryForm.compte_tiers} onChange={(event) => setEntryForm({ ...entryForm, compte_tiers: event.target.value })} className={INPUT_CLASS} required>
                  <option value="">Sélectionner un compte</option>
                  {thirdPartyAccounts.map((account) => <option key={account.id} value={account.numero_compte}>{account.numero_compte} — {account.libelle}</option>)}
                </select>
              </label>

              <label>
                <FieldLabel>Compte HT</FieldLabel>
                <select value={entryForm.compte_ht} onChange={(event) => setEntryForm({ ...entryForm, compte_ht: event.target.value })} className={INPUT_CLASS} required>
                  <option value="">Sélectionner un compte</option>
                  {htAccounts.map((account) => <option key={account.id} value={account.numero_compte}>{account.numero_compte} — {account.libelle}</option>)}
                </select>
              </label>

              <label>
                <FieldLabel>Compte TVA</FieldLabel>
                <select value={entryForm.compte_tva} onChange={(event) => setEntryForm({ ...entryForm, compte_tva: event.target.value })} className={INPUT_CLASS} required={Number(entryForm.montant_tva) > 0}>
                  <option value="">{Number(entryForm.montant_tva) > 0 ? "Sélectionner un compte" : "TVA non applicable"}</option>
                  {vatAccounts.map((account) => <option key={account.id} value={account.numero_compte}>{account.numero_compte} — {account.libelle}</option>)}
                </select>
              </label>

              {planAccounts.length === 0 && (
                <div className="sm:col-span-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  Le plan comptable de cette entreprise est vide. Ajoutez d’abord les comptes exacts nécessaires.
                  <button type="button" onClick={() => navigate(`/plan-comptable?entreprise_id=${detail.entreprise_id ?? ""}`)} className="ml-2 font-bold text-blue-700 underline">Ouvrir le plan comptable</button>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setIsEntryModalOpen(false)}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={currentAction === "save-entry"}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-5 py-2 text-sm font-bold text-white hover:bg-blue-800 disabled:opacity-50"
              >
                <Save size={16} />
                Enregistrer
              </button>
            </div>
          </form>
        </div>
      )}

      {movementForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <form
            onSubmit={(event) => void saveMovement(event)}
            className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl"
          >
            <div className="mb-5 flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Modifier le mouvement bancaire
                </h2>
                <p className="text-xs text-slate-500">
                  Corrigez la ligne extraite depuis le relevé.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMovementForm(null)}
                className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
              >
                <X size={19} />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label>
                <FieldLabel>Date</FieldLabel>
                <TextInput
                  type="date"
                  required
                  value={movementForm.date_operation}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      date_operation: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Type</FieldLabel>
                <select
                  value={movementForm.type_mouvement}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      type_mouvement: event.target.value as TypeMouvementBancaire,
                    })
                  }
                  className={INPUT_CLASS}
                >
                  <option value="debit">Débit</option>
                  <option value="credit">Crédit</option>
                </select>
              </label>

              <label className="sm:col-span-2">
                <FieldLabel>Libellé</FieldLabel>
                <TextInput
                  required
                  value={movementForm.libelle}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      libelle: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Référence</FieldLabel>
                <TextInput
                  value={movementForm.reference}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      reference: event.target.value,
                    })
                  }
                />
              </label>

              <label>
                <FieldLabel>Montant</FieldLabel>
                <TextInput
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={movementForm.montant}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      montant: event.target.value,
                    })
                  }
                />
              </label>

              <label className="sm:col-span-2">
                <FieldLabel>Solde après opération</FieldLabel>
                <TextInput
                  type="number"
                  step="0.01"
                  value={movementForm.solde_apres_operation}
                  onChange={(event) =>
                    setMovementForm({
                      ...movementForm,
                      solde_apres_operation: event.target.value,
                    })
                  }
                />
              </label>
            </div>

            <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setMovementForm(null)}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
              >
                Annuler
              </button>
              <button
                type="submit"
                disabled={currentAction === "save-movement"}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-5 py-2 text-sm font-bold text-white hover:bg-blue-800 disabled:opacity-50"
              >
                <Save size={16} />
                Enregistrer
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
