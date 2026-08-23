import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  CheckCircle2,
  Download,
  ExternalLink,
  FileSearch,
  Landmark,
  Link2,
  Link2Off,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Upload,
  X,
} from "lucide-react";

import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import {
  confirmBankMovementAllocations,
  getBankMovementCandidates,
  getInternalTransferCandidates,
  linkInternalTransfer,
  listBankAccounts,
  listBankMovements,
  reconcileBankMovementAuto,
  updateBankOperation,
  unlinkBankMovementReconciliation,
} from "../api/accountingApi";
import {
  openDocumentFile,
  toggleDocumentSaisie,
  updateBankMovement,
} from "../api/documentsApi";
import type { Entreprise } from "../types/entreprise";
import type {
  CompteBancaireEntreprise,
  MouvementBancaireListe,
  NatureOperationBancaire,
  RapprochementCandidat,
  TypeMouvementBancaire,
  VirementInterneCandidat,
} from "../types/mouvementBancaire";
import {
  exportRowsToCsv,
  exportRowsToExcel,
  type ExportColumn,
} from "../utils/tableExport";

const MOIS = [
  "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

interface EditForm {
  id: string;
  documentId: string;
  dateOperation: string;
  libelle: string;
  reference: string;
  typeMouvement: TypeMouvementBancaire;
  montant: string;
  solde: string;
}

interface CandidateModal {
  movement: MouvementBancaireListe;
  candidates: RapprochementCandidat[];
  loading: boolean;
  amounts: Record<string, string>;
}

interface OperationModalState {
  movement: MouvementBancaireListe;
  nature: NatureOperationBancaire;
  compteContrepartie: string;
  bankAccountId: string;
  accounts: CompteBancaireEntreprise[];
  transferCandidates: VirementInterneCandidat[];
  loading: boolean;
}

function normalizeType(value: string): TypeMouvementBancaire {
  return value.toLowerCase() === "credit" ? "credit" : "debit";
}

function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === "") return 0;
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value: string | number | null | undefined): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "MAD",
    minimumFractionDigits: 2,
  }).format(toNumber(value));
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("fr-FR");
}

function apiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Une erreur inattendue s’est produite.";
  if (!error.response) return "Backend inaccessible. Vérifiez Uvicorn.";
  const detail = error.response.data?.detail;
  return typeof detail === "string" ? detail : `Erreur API ${error.response.status}.`;
}

function rapprochementLabel(status: string): string {
  const labels: Record<string, string> = {
    non_rapproche: "Non rapproché",
    propose: "Proposé",
    automatique: "Auto",
    confirme: "Confirmé",
    ambigu: "Ambigu",
  };
  return labels[status] ?? status;
}

function rapprochementClass(status: string): string {
  if (status === "confirme") return "border-green-200 bg-green-50 text-green-700";
  if (status === "automatique") return "border-blue-200 bg-blue-50 text-blue-700";
  if (status === "propose") return "border-amber-200 bg-amber-50 text-amber-700";
  if (status === "ambigu") return "border-violet-200 bg-violet-50 text-violet-700";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

export function RelevesBancairesPage() {
  const navigate = useNavigate();

  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [mouvements, setMouvements] = useState<MouvementBancaireListe[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [annee, setAnnee] = useState<number | "">("");
  const [mois, setMois] = useState<number | "">("");
  const [recherche, setRecherche] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [candidateModal, setCandidateModal] = useState<CandidateModal | null>(null);
  const [operationModal, setOperationModal] = useState<OperationModalState | null>(null);

  useEffect(() => {
    listAvailableEntreprises("banque").then((items) => {
      setEntreprises(items);
      setEntrepriseId((current) => chooseAvailableEntreprise(items, current));
    }).catch(() => setEntreprises([]));
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listBankMovements({
        entreprise_id: entrepriseId || undefined,
        recherche: recherche.trim() || undefined,
        annee: annee || undefined,
        mois: mois || undefined,
      });
      setMouvements(data);
    } catch (requestError) {
      setMouvements([]);
      setError(apiErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [entrepriseId, recherche, annee, mois]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 250);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const anneesDisponibles = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const years = new Set<number>([currentYear]);
    mouvements.forEach((movement) => {
      if (movement.annee) years.add(movement.annee);
      else years.add(new Date(`${movement.date_operation}T00:00:00`).getFullYear());
    });
    return [...years].sort((a, b) => b - a);
  }, [mouvements]);

  const totaux = useMemo(() => {
    let depot = 0;
    let retrait = 0;
    let rapproches = 0;
    let ambigus = 0;
    const documents = new Set<string>();

    for (const movement of mouvements) {
      documents.add(movement.document_id);
      if (normalizeType(movement.type_mouvement) === "credit") depot += toNumber(movement.montant);
      else retrait += toNumber(movement.montant);

      if (["automatique", "confirme"].includes(movement.statut_rapprochement)) rapproches += 1;
      if (movement.statut_rapprochement === "ambigu") ambigus += 1;
    }

    return { depot, retrait, documents: documents.size, rapproches, ambigus };
  }, [mouvements]);

  const exportColumns: ExportColumn<MouvementBancaireListe>[] = [
    { header: "Entreprise", value: (row) => row.entreprise_nom ?? "" },
    { header: "Date", value: (row) => formatDate(row.date_operation) },
    { header: "Fichier", value: (row) => row.nom_fichier_document },
    { header: "Libellé", value: (row) => row.libelle },
    { header: "Référence", value: (row) => row.reference ?? "" },
    { header: "Type", value: (row) => normalizeType(row.type_mouvement) === "credit" ? "Dépôt" : "Retrait" },
    { header: "Montant", value: (row) => toNumber(row.montant) },
    { header: "Rapprochement", value: (row) => rapprochementLabel(row.statut_rapprochement) },
    { header: "N° facture liée", value: (row) => row.numero_piece_rapprochee ?? "" },
    { header: "Tiers lié", value: (row) => row.tiers_rapproche ?? "" },
    { header: "Compte banque", value: (row) => row.compte_banque ?? "" },
  ];

  function openEdit(movement: MouvementBancaireListe): void {
    setEditing({
      id: movement.id,
      documentId: movement.document_id,
      dateOperation: movement.date_operation,
      libelle: movement.libelle,
      reference: movement.reference ?? "",
      typeMouvement: normalizeType(movement.type_mouvement),
      montant: String(movement.montant),
      solde: movement.solde_apres_operation == null ? "" : String(movement.solde_apres_operation),
    });
  }

  async function saveEdit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      await updateBankMovement(editing.documentId, editing.id, {
        date_operation: editing.dateOperation,
        libelle: editing.libelle.trim(),
        reference: editing.reference.trim() || null,
        type_mouvement: editing.typeMouvement,
        montant: editing.montant,
        solde_apres_operation: editing.solde || null,
      });
      setEditing(null);
      setSuccess("Mouvement corrigé et rapprochement recalculé.");
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function toggleSaisie(movement: MouvementBancaireListe): Promise<void> {
    setActionId(movement.document_id);
    setError(null);
    try {
      const result = await toggleDocumentSaisie(movement.document_id);
      setMouvements((current) => current.map((item) =>
        item.document_id === movement.document_id
          ? { ...item, saisie_topaze: result.saisie_topaze }
          : item,
      ));
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function autoReconcile(movement: MouvementBancaireListe): Promise<void> {
    setActionId(movement.id);
    setError(null);
    try {
      await reconcileBankMovementAuto(movement.id);
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function openCandidates(movement: MouvementBancaireListe): Promise<void> {
    setCandidateModal({ movement, candidates: [], loading: true, amounts: {} });
    try {
      const candidates = await getBankMovementCandidates(movement.id);
      setCandidateModal({ movement, candidates, loading: false, amounts: {} });
    } catch (requestError) {
      setCandidateModal(null);
      setError(apiErrorMessage(requestError));
    }
  }

  async function openOperationModal(movement: MouvementBancaireListe): Promise<void> {
    setOperationModal({
      movement,
      nature: (movement.nature_operation || "reglement_facture") as NatureOperationBancaire,
      compteContrepartie: movement.compte_contrepartie ?? "",
      bankAccountId: movement.compte_bancaire_entreprise_id ?? "",
      accounts: [],
      transferCandidates: [],
      loading: true,
    });
    try {
      const accounts = await listBankAccounts(movement.entreprise_id);
      const transferCandidates = movement.nature_operation === "virement_interne"
        ? await getInternalTransferCandidates(movement.id)
        : [];
      setOperationModal((current) => current && current.movement.id === movement.id
        ? { ...current, accounts, transferCandidates, loading: false }
        : current);
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
      setOperationModal((current) => current ? { ...current, loading: false } : current);
    }
  }

  async function saveOperation(): Promise<void> {
    if (!operationModal) return;
    setActionId(operationModal.movement.id);
    setError(null);
    try {
      await updateBankOperation(operationModal.movement.id, {
        nature_operation: operationModal.nature,
        compte_contrepartie: operationModal.compteContrepartie.trim() || null,
        compte_bancaire_entreprise_id: operationModal.bankAccountId || null,
      });
      if (operationModal.nature === "virement_interne") {
        const transferCandidates = await getInternalTransferCandidates(operationModal.movement.id);
        setOperationModal({ ...operationModal, transferCandidates, loading: false });
        setSuccess("Nature enregistrée. Choisissez maintenant le mouvement opposé du virement interne.");
      } else {
        setOperationModal(null);
        setSuccess("Nature bancaire enregistrée.");
      }
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function chooseInternalTransfer(otherMovementId: string): Promise<void> {
    if (!operationModal) return;
    setActionId(operationModal.movement.id);
    setError(null);
    try {
      await linkInternalTransfer(operationModal.movement.id, otherMovementId);
      setOperationModal(null);
      setSuccess("Virement interne lié et écriture Banque synchronisée.");
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function confirmProposedAllocations(movement: MouvementBancaireListe): Promise<void> {
    if (!movement.allocations.length) return;
    setActionId(movement.id);
    setError(null);
    try {
      await confirmBankMovementAllocations(
        movement.id,
        movement.allocations.map((allocation) => ({
          ecriture_id: allocation.ecriture_id,
          montant_affecte: allocation.montant_affecte,
        })),
      );
      setSuccess(
        movement.mode_rapprochement === "groupe"
          ? "Règlement groupé confirmé."
          : movement.mode_rapprochement === "partiel"
            ? "Paiement partiel confirmé."
            : "Rapprochement confirmé.",
      );
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function confirmManualAllocations(): Promise<void> {
    if (!candidateModal) return;
    const allocations = candidateModal.candidates
      .map((candidate) => ({
        ecriture_id: candidate.ecriture_id,
        montant_affecte: candidateModal.amounts[candidate.ecriture_id] ?? "",
      }))
      .filter((item) => toNumber(item.montant_affecte) > 0);

    if (allocations.length === 0) {
      setError("Saisissez au moins un montant à affecter.");
      return;
    }

    const total = allocations.reduce((sum, item) => sum + toNumber(item.montant_affecte), 0);
    if (Math.abs(total - toNumber(candidateModal.movement.montant)) > 0.01) {
      setError(`Le total affecté doit être égal au mouvement : ${formatMoney(candidateModal.movement.montant)}.`);
      return;
    }

    setActionId(candidateModal.movement.id);
    setError(null);
    try {
      await confirmBankMovementAllocations(candidateModal.movement.id, allocations);
      setCandidateModal(null);
      setSuccess(allocations.length > 1 ? "Règlement groupé confirmé." : "Affectation confirmée.");
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  async function unlinkReconciliation(movement: MouvementBancaireListe): Promise<void> {
    setActionId(movement.id);
    try {
      await unlinkBankMovementReconciliation(movement.id);
      setSuccess("Rapprochement annulé.");
      await refresh();
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  }

  const exportName = `banque_${annee || "toutes"}_${mois || "tous_mois"}`;

  return (
    <div className="min-h-full bg-[#F8F9FB] p-5 text-slate-800 lg:p-8">
      <div className="mx-auto max-w-[1800px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Banque — rapprochement facture/paiement</h1>
            <p className="mt-1 text-sm text-slate-500">
              Les mouvements restent issus du relevé. Le rapprochement ne crée aucune écriture bancaire fictive.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => navigate("/comptes-bancaires")} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><Landmark size={16} /> Comptes bancaires</button>
            <button type="button" onClick={() => navigate("/upload")} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"><Upload size={16} /> Importer</button>
            <button type="button" onClick={() => exportRowsToCsv(`${exportName}.csv`, mouvements, exportColumns)} disabled={!mouvements.length} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"><Download size={16} /> CSV</button>
            <button type="button" onClick={() => exportRowsToExcel(`${exportName}.xls`, "Banque", mouvements, exportColumns)} disabled={!mouvements.length} className="inline-flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"><Download size={16} /> Excel</button>
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <section className="mb-5 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:grid-cols-4">
          <label className="block"><span className="mb-1 block text-xs font-bold uppercase text-slate-500">Entreprise</span><select value={entrepriseId} onChange={(e) => setEntrepriseId(e.target.value)} className="w-full rounded-lg border px-3 py-2.5 text-sm"><option value="">Toutes</option>{entreprises.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}</select>{entreprises.length === 0 && <span className="mt-2 block text-xs text-amber-700">Aucune entreprise ne possÃ¨de encore de donnÃ©es dans ce module.</span>}</label>
          <label className="block"><span className="mb-1 block text-xs font-bold uppercase text-slate-500">Année</span><select value={annee} onChange={(e) => setAnnee(e.target.value ? Number(e.target.value) : "")} className="w-full rounded-lg border px-3 py-2.5 text-sm"><option value="">Toutes</option>{anneesDisponibles.map((year) => <option key={year}>{year}</option>)}</select></label>
          <label className="block"><span className="mb-1 block text-xs font-bold uppercase text-slate-500">Mois</span><select value={mois} onChange={(e) => setMois(e.target.value ? Number(e.target.value) : "")} className="w-full rounded-lg border px-3 py-2.5 text-sm"><option value="">Tous</option>{MOIS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label>
          <label className="block"><span className="mb-1 block text-xs font-bold uppercase text-slate-500">Recherche</span><div className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={recherche} onChange={(e) => setRecherche(e.target.value)} className="w-full rounded-lg border py-2.5 pl-9 pr-3 text-sm" placeholder="libellé, référence..." /></div></label>
        </section>

        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-slate-400">Dépôts</p><strong className="text-green-700">{formatMoney(totaux.depot)}</strong></div>
          <div className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-slate-400">Retraits</p><strong className="text-red-600">{formatMoney(totaux.retrait)}</strong></div>
          <div className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-slate-400">Rapprochés</p><strong>{totaux.rapproches}</strong></div>
          <div className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-slate-400">Ambigus</p><strong className="text-violet-700">{totaux.ambigus}</strong></div>
          <div className="rounded-xl border bg-white p-4"><p className="text-xs uppercase text-slate-400">Relevés</p><strong>{totaux.documents}</strong></div>
        </div>

        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1550px] text-left text-sm">
              <thead className="border-b bg-slate-50 text-xs font-semibold uppercase text-slate-500"><tr>
                <th className="px-4 py-3">Fichier</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Libellé</th><th className="px-4 py-3">Type</th><th className="px-4 py-3 text-right">Dépôt</th><th className="px-4 py-3 text-right">Retrait</th><th className="px-4 py-3">Rapprochement</th><th className="px-4 py-3">Facture liée</th><th className="px-4 py-3">Compte banque</th><th className="px-4 py-3 text-center">Saisie</th><th className="px-4 py-3">Actions</th>
              </tr></thead>
              <tbody className="divide-y divide-slate-100">
                {loading && <tr><td colSpan={11} className="px-4 py-12 text-center text-slate-400">Chargement...</td></tr>}
                {!loading && mouvements.map((movement) => {
                  const type = normalizeType(movement.type_mouvement);
                  const hasLink = Boolean(movement.ecriture_rapprochee_id);
                  return <tr key={movement.id} className="hover:bg-slate-50/70">
                    <td className="max-w-[170px] truncate px-4 py-3 text-xs font-semibold text-green-700" title={movement.nom_fichier_document}>{movement.nom_fichier_document}</td>
                    <td className="px-4 py-3 text-xs font-semibold">{formatDate(movement.date_operation)}</td>
                    <td className="max-w-[300px] whitespace-normal px-4 py-3 text-xs leading-5">{movement.libelle}</td>
                    <td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[11px] font-bold ${type === "credit" ? "border-green-100 bg-green-50 text-green-700" : "border-red-100 bg-red-50 text-red-700"}`}>{type === "credit" ? "Dépôt" : "Retrait"}</span></td>
                    <td className="px-4 py-3 text-right text-xs font-bold text-green-700">{type === "credit" ? formatMoney(movement.montant) : "—"}</td>
                    <td className="px-4 py-3 text-right text-xs font-bold text-red-600">{type === "debit" ? formatMoney(movement.montant) : "—"}</td>
                    <td className="px-4 py-3"><span title={movement.raison_rapprochement ?? undefined} className={`rounded-full border px-2 py-1 text-[11px] font-bold ${rapprochementClass(movement.statut_rapprochement)}`}>{rapprochementLabel(movement.statut_rapprochement)}{movement.mode_rapprochement && movement.mode_rapprochement !== "simple" ? ` · ${movement.mode_rapprochement}` : ""}{movement.score_rapprochement != null ? ` ${Math.round(toNumber(movement.score_rapprochement))}%` : ""}</span></td>
                    <td className="max-w-[280px] px-4 py-3 text-xs">{movement.allocations.length > 0 ? <div className="space-y-1">{movement.allocations.map((allocation) => <div key={allocation.id}><strong>{allocation.numero_piece ?? "Facture"}</strong> <span className="text-slate-500">· {formatMoney(allocation.montant_affecte)}</span><div className="text-slate-400">{allocation.tiers ?? "—"} · {allocation.statut}</div></div>)}</div> : hasLink ? <div><strong>{movement.numero_piece_rapprochee ?? "Facture"}</strong><div className="text-slate-500">{movement.tiers_rapproche ?? "—"} · {formatDate(movement.date_piece_rapprochee)}</div></div> : "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs">{movement.compte_banque ?? "À configurer"}</td>
                    <td className="px-4 py-3 text-center"><input type="checkbox" checked={movement.saisie_topaze} disabled={actionId === movement.document_id} onChange={() => void toggleSaisie(movement)} className="h-4 w-4 accent-green-600" /></td>
                    <td className="px-4 py-3"><div className="flex flex-wrap gap-1">
                      <button type="button" onClick={() => navigate(`/documents/${movement.document_id}`)} className="rounded px-2 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"><FileSearch size={14} className="inline" /> Vérifier</button>
                      <button type="button" onClick={() => openEdit(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50"><Pencil size={14} className="inline" /> Modifier</button>
                      <button type="button" onClick={() => void openOperationModal(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"><Landmark size={14} className="inline" /> Nature</button>
                      {movement.statut_rapprochement === "propose" && movement.allocations.length > 0 && <button type="button" disabled={actionId === movement.id} onClick={() => void confirmProposedAllocations(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"><CheckCircle2 size={14} className="inline" /> Confirmer {movement.mode_rapprochement === "groupe" ? "groupe" : movement.mode_rapprochement === "partiel" ? "partiel" : ""}</button>}
                      {movement.statut_rapprochement === "ambigu" && <button type="button" onClick={() => void openCandidates(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-50"><Link2 size={14} className="inline" /> Candidats</button>}
                      {!hasLink && movement.statut_rapprochement !== "ambigu" && <button type="button" disabled={actionId === movement.id} onClick={() => void autoReconcile(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"><RefreshCw size={14} className="inline" /> Rapprocher</button>}
                      {hasLink && ["automatique", "confirme"].includes(movement.statut_rapprochement) && <button type="button" onClick={() => void unlinkReconciliation(movement)} className="rounded px-2 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"><Link2Off size={14} className="inline" /> Délier</button>}
                      <button type="button" onClick={() => void openDocumentFile(movement.document_id)} className="rounded px-2 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"><ExternalLink size={14} className="inline" /> Fichier</button>
                    </div></td>
                  </tr>;
                })}
                {!loading && mouvements.length === 0 && <tr><td colSpan={11} className="px-4 py-14 text-center text-slate-400"><Landmark size={32} className="mx-auto mb-2" />Aucun mouvement.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {editing && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"><form onSubmit={(event) => void saveEdit(event)} className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl"><div className="mb-5 flex items-center justify-between border-b pb-4"><div><h2 className="text-lg font-bold">Modifier le mouvement bancaire</h2><p className="text-xs text-slate-500">La modification relance le rapprochement.</p></div><button type="button" onClick={() => setEditing(null)} className="rounded p-2 hover:bg-slate-100"><X size={18} /></button></div><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm">Date<input type="date" required value={editing.dateOperation} onChange={(e) => setEditing({ ...editing, dateOperation: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="text-sm">Type<select value={editing.typeMouvement} onChange={(e) => setEditing({ ...editing, typeMouvement: e.target.value as TypeMouvementBancaire })} className="mt-1 w-full rounded-lg border px-3 py-2"><option value="credit">Dépôt / Crédit</option><option value="debit">Retrait / Débit</option></select></label><label className="text-sm sm:col-span-2">Libellé<input required value={editing.libelle} onChange={(e) => setEditing({ ...editing, libelle: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="text-sm">Référence<input value={editing.reference} onChange={(e) => setEditing({ ...editing, reference: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="text-sm">Montant<input type="number" min="0" step="0.01" required value={editing.montant} onChange={(e) => setEditing({ ...editing, montant: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label><label className="text-sm sm:col-span-2">Solde après opération<input type="number" step="0.01" value={editing.solde} onChange={(e) => setEditing({ ...editing, solde: e.target.value })} className="mt-1 w-full rounded-lg border px-3 py-2" /></label></div><div className="mt-6 flex justify-end gap-2 border-t pt-4"><button type="button" onClick={() => setEditing(null)} className="rounded-lg px-4 py-2 text-sm hover:bg-slate-100">Annuler</button><button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Save size={16} /> Enregistrer</button></div></form></div>}

      {operationModal && (
        <div className="fixed inset-0 z-[105] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-3xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-5 flex items-center justify-between border-b pb-4">
              <div>
                <h2 className="text-lg font-bold">Nature de l’opération bancaire</h2>
                <p className="text-sm text-slate-500">{operationModal.movement.libelle} · {formatMoney(operationModal.movement.montant)}</p>
              </div>
              <button type="button" onClick={() => setOperationModal(null)} className="rounded p-2 hover:bg-slate-100"><X size={18} /></button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Nature
                <select
                  value={operationModal.nature}
                  onChange={(event) => setOperationModal({
                    ...operationModal,
                    nature: event.target.value as NatureOperationBancaire,
                  })}
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                >
                  <option value="reglement_facture">Règlement de facture</option>
                  <option value="acompte">Acompte / avance</option>
                  <option value="frais_bancaire">Frais bancaire</option>
                  <option value="virement_interne">Virement interne</option>
                  <option value="autre">Autre opération</option>
                </select>
              </label>

              <label className="text-sm font-medium">
                Compte bancaire
                <select
                  value={operationModal.bankAccountId}
                  onChange={(event) => setOperationModal({ ...operationModal, bankAccountId: event.target.value })}
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                >
                  <option value="">Détection automatique / non configuré</option>
                  {operationModal.accounts.map((account) => (
                    <option key={account.id} value={account.id}>{account.libelle} — {account.numero_compte_comptable}</option>
                  ))}
                </select>
              </label>

              {!["reglement_facture", "virement_interne"].includes(operationModal.nature) && (
                <label className="text-sm font-medium sm:col-span-2">
                  Compte de contrepartie exact
                  <input
                    value={operationModal.compteContrepartie}
                    onChange={(event) => setOperationModal({ ...operationModal, compteContrepartie: event.target.value })}
                    placeholder="Compte existant dans le plan comptable"
                    className="mt-1 w-full rounded-lg border px-3 py-2 font-mono"
                  />
                  <span className="mt-1 block text-xs text-slate-400">ComptaFlow ne crée aucun compte automatiquement pour les frais/acompte/autres opérations.</span>
                </label>
              )}
            </div>

            <div className="mt-5 flex justify-end gap-2 border-t pt-4">
              <button type="button" onClick={() => setOperationModal(null)} className="rounded-lg px-4 py-2 text-sm hover:bg-slate-100">Annuler</button>
              <button type="button" disabled={operationModal.loading || actionId === operationModal.movement.id} onClick={() => void saveOperation()} className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Enregistrer</button>
            </div>

            {operationModal.nature === "virement_interne" && operationModal.transferCandidates.length > 0 && (
              <div className="mt-5 border-t pt-4">
                <h3 className="mb-3 text-sm font-bold">Mouvements opposés candidats</h3>
                <div className="space-y-2">
                  {operationModal.transferCandidates.map((candidate) => (
                    <div key={candidate.mouvement_id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                      <div className="text-sm">
                        <strong>{formatDate(candidate.date_operation)} · {formatMoney(candidate.montant)}</strong>
                        <div className="text-xs text-slate-500">{candidate.libelle}</div>
                        <div className="text-xs text-slate-400">Compte {candidate.compte_banque ?? "non configuré"} · score {Math.round(toNumber(candidate.score))}%</div>
                      </div>
                      <button type="button" onClick={() => void chooseInternalTransfer(candidate.mouvement_id)} className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white">Lier</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {candidateModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-4xl rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between border-b pb-4">
              <div>
                <h2 className="text-lg font-bold">Affecter le mouvement aux factures</h2>
                <p className="text-sm text-slate-500">
                  Mouvement : {formatMoney(candidateModal.movement.montant)} — {candidateModal.movement.libelle}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Paiement partiel : affectez tout le mouvement à une partie du solde d'une facture. Règlement groupé : répartissez le mouvement sur plusieurs factures.
                </p>
              </div>
              <button onClick={() => setCandidateModal(null)} className="rounded p-2 hover:bg-slate-100"><X size={18} /></button>
            </div>

            {candidateModal.loading ? (
              <p className="py-8 text-center text-slate-400">Recherche...</p>
            ) : candidateModal.candidates.length === 0 ? (
              <p className="py-8 text-center text-slate-400">Aucun candidat compatible.</p>
            ) : (
              <div className="max-h-[55vh] space-y-3 overflow-y-auto pr-1">
                {candidateModal.candidates.map((candidate) => (
                  <div key={candidate.ecriture_id} className="grid gap-3 rounded-xl border p-4 md:grid-cols-[1fr_170px] md:items-center">
                    <div>
                      <div className="font-bold">{candidate.numero_piece ?? "Sans numéro"} — {candidate.tiers ?? "Tiers inconnu"}</div>
                      <div className="mt-1 text-sm text-slate-500">
                        {formatDate(candidate.date_piece)} · TTC {formatMoney(candidate.montant_ttc)} · déjà réglé {formatMoney(candidate.montant_deja_regle)} · reste {formatMoney(candidate.montant_restant)}
                      </div>
                      <div className="mt-1 text-xs font-semibold text-green-700">
                        Suggestion : {candidate.type_suggestion} · {formatMoney(candidate.montant_suggere)} · score {Math.round(toNumber(candidate.score))}%
                      </div>
                      <div className="mt-1 text-xs text-slate-400">{candidate.raisons.join(" ")}</div>
                    </div>
                    <label className="text-xs font-semibold text-slate-600">
                      Montant affecté
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        max={String(candidate.montant_restant)}
                        value={candidateModal.amounts[candidate.ecriture_id] ?? ""}
                        onChange={(event) => setCandidateModal({
                          ...candidateModal,
                          amounts: {
                            ...candidateModal.amounts,
                            [candidate.ecriture_id]: event.target.value,
                          },
                        })}
                        placeholder={String(candidate.montant_suggere)}
                        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setCandidateModal({
                          ...candidateModal,
                          amounts: {
                            ...candidateModal.amounts,
                            [candidate.ecriture_id]: String(candidate.montant_suggere),
                          },
                        })}
                        className="mt-1 text-[11px] text-green-700 hover:underline"
                      >
                        Utiliser la suggestion
                      </button>
                    </label>
                  </div>
                ))}
              </div>
            )}

            {!candidateModal.loading && candidateModal.candidates.length > 0 && (
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                <div className="text-sm text-slate-600">
                  Total saisi : <strong>{formatMoney(Object.values(candidateModal.amounts).reduce((sum, value) => sum + toNumber(value), 0))}</strong>
                  <span className="mx-2">/</span>
                  Mouvement : <strong>{formatMoney(candidateModal.movement.montant)}</strong>
                </div>
                <button
                  type="button"
                  disabled={actionId === candidateModal.movement.id}
                  onClick={() => void confirmManualAllocations()}
                  className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Confirmer les affectations
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
