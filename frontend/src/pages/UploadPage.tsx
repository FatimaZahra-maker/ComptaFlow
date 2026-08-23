import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  ExternalLink,
  FileSearch,
  FileUp,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from "lucide-react";

import {
  deleteDocument,
  openDocumentFile,
  listDocuments,
  retraiterDocument,
  uploadDocument,
} from "../api/documentsApi";

import type { Document } from "../types/document";

const STATUS_LABELS: Record<string, string> = {
  en_attente: "En attente",
  en_traitement: "En traitement",
  traite: "Traité",
  valide: "Validé",
  erreur: "Erreur",
};

const STATUS_CLASSES: Record<string, string> = {
  en_attente: "bg-slate-100 text-slate-700",
  en_traitement: "bg-amber-100 text-amber-700",
  traite: "bg-blue-100 text-blue-700",
  valide: "bg-green-100 text-green-700",
  erreur: "bg-red-100 text-red-700",
  doublon: "bg-violet-100 text-violet-700",
};

const ACCEPTED_TYPES = [
  "application/pdf",
  "image/png",
  "image/jpeg",
];

const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
];

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible. Vérifiez Uvicorn.";
  }
  return "L'opération a échoué.";
}

function formatFileSize(bytes?: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_TYPES.includes(file.type)) return true;

  const lowerName = file.name.toLocaleLowerCase("fr");
  return ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension));
}

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
  const [currentUploadName, setCurrentUploadName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [currentAction, setCurrentAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await listDocuments();
      setDocuments(data);
    } catch (requestError) {
      if (!silent) setError(getErrorMessage(requestError));
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(true), 5_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const filteredDocuments = useMemo(() => {
    const term = searchTerm.trim().toLocaleLowerCase("fr");
    if (!term) return documents;
    return documents.filter((document) => [
      document.nom_fichier_original,
      document.categorie,
      document.statut,
      document.est_doublon ? "doublon" : null,
    ].some((value) => value?.toLocaleLowerCase("fr").includes(term)));
  }, [documents, searchTerm]);

  const stats = useMemo(() => ({
    total: documents.length,
    pending: documents.filter((document) => ["en_attente", "en_traitement"].includes(document.statut)).length,
    processed: documents.filter(
      (document) => !document.est_doublon && ["traite", "valide"].includes(document.statut),
    ).length,
    errors: documents.filter((document) => document.statut === "erreur").length,
  }), [documents]);

  const uploadButtonLabel = useMemo(() => {
    if (!uploading) return "Choisir des fichiers";

    if (uploadProgress.total <= 1) {
      return "Import en cours...";
    }

    return `Import ${uploadProgress.current}/${uploadProgress.total}`;
  }, [uploadProgress, uploading]);

  async function uploadFiles(files: File[]) {
    if (files.length === 0 || uploading) return;

    const acceptedFiles = files.filter(isAcceptedFile);
    const rejectedFiles = files.filter((file) => !isAcceptedFile(file));

    setError(null);
    setSuccess(null);

    if (acceptedFiles.length === 0) {
      setError("Aucun fichier valide. Utilisez PDF, PNG ou JPEG.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }

    setUploading(true);
    setUploadProgress({ current: 0, total: acceptedFiles.length });
    setCurrentUploadName(null);

    const failedFiles: string[] = [];
    let importedCount = 0;

    try {
      for (let index = 0; index < acceptedFiles.length; index += 1) {
        const file = acceptedFiles[index];

        setCurrentUploadName(file.name);
        setUploadProgress({
          current: index + 1,
          total: acceptedFiles.length,
        });

        try {
          await uploadDocument(file);
          importedCount += 1;
        } catch (requestError) {
          failedFiles.push(`${file.name} : ${getErrorMessage(requestError)}`);
        }
      }

      await refresh();

      const messages: string[] = [];

      if (importedCount > 0) {
        messages.push(
          importedCount === 1
            ? "1 document importé. Le traitement a été lancé."
            : `${importedCount} documents importés. Les traitements ont été lancés.`,
        );
      }

      if (rejectedFiles.length > 0) {
        messages.push(
          `${rejectedFiles.length} fichier(s) ignoré(s) car le format n'est pas autorisé.`,
        );
      }

      if (messages.length > 0) {
        setSuccess(messages.join(" "));
      }

      if (failedFiles.length > 0) {
        setError(
          `Échec pour ${failedFiles.length} fichier(s) : ${failedFiles.join(" | ")}`,
        );
      }
    } finally {
      setUploading(false);
      setUploadProgress({ current: 0, total: 0 });
      setCurrentUploadName(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) void uploadFiles(files);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);

    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) void uploadFiles(files);
  }

  async function handleRetraiter(document: Document) {
    if (!window.confirm(`Relancer le traitement de « ${document.nom_fichier_original} » ?`)) return;
    setCurrentAction(`retry-${document.id}`);
    setError(null);
    setSuccess(null);
    try {
      await retraiterDocument(document.id);
      await refresh();
      setSuccess("Retraitement lancé.");
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setCurrentAction(null);
    }
  }

  async function handleDelete(document: Document) {
    if (!window.confirm(
      `Supprimer définitivement « ${document.nom_fichier_original} » ?\n\n` +
      "Vous pourrez ensuite réimporter le même fichier.",
    )) return;

    setCurrentAction(`delete-${document.id}`);
    setError(null);
    setSuccess(null);
    try {
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setSuccess("Document supprimé définitivement.");
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setCurrentAction(null);
    }
  }

  return (
    <div className="min-h-full bg-slate-50 p-5 lg:p-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Documents</h1>
            <p className="mt-1 text-sm text-slate-500">
              Import, suivi du traitement et contrôle des pièces comptables.
            </p>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-green-700 disabled:opacity-50"
          >
            <FileUp size={17} />
            {uploading ? uploadButtonLabel : "Importer des documents"}
          </button>
        </div>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {success && <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

        <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Documents reçus", stats.total],
            ["À traiter", stats.pending],
            ["Traités", stats.processed],
            ["En anomalie", stats.errors],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
              <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-5 xl:grid-cols-[1fr_330px]">
          <section className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="relative w-full max-w-lg">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
                <input
                  type="search"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Rechercher un document..."
                  className="w-full rounded-lg border border-slate-300 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-green-500 focus:ring-4 focus:ring-green-500/10"
                />
              </div>
              <button
                type="button"
                onClick={() => void refresh()}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
                Actualiser
              </button>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-sm">
                  <thead className="border-b bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Date de réception</th>
                      <th className="px-4 py-3">Fichier</th>
                      <th className="px-4 py-3">Catégorie</th>
                      <th className="px-4 py-3">Période</th>
                      <th className="px-4 py-3">Statut</th>
                      <th className="px-4 py-3">Taille</th>
                      <th className="px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && (
                      <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-400">Chargement...</td></tr>
                    )}
                    {!loading && filteredDocuments.map((document) => (
                      <tr key={document.id} className="border-b last:border-0 hover:bg-slate-50/70">
                        <td className="px-4 py-3">{new Date(document.created_at).toLocaleString("fr-FR")}</td>
                        <td className="max-w-[220px] truncate px-4 py-3 font-semibold text-slate-800" title={document.nom_fichier_original}>
                          {document.nom_fichier_original}
                        </td>
                        <td className="px-4 py-3 capitalize">{document.categorie ?? "À déterminer"}</td>
                        <td className="px-4 py-3">
                          {document.annee ? `${String(document.mois ?? "—").padStart(2, "0")}/${document.annee}` : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                              document.est_doublon
                                ? STATUS_CLASSES.doublon
                                : STATUS_CLASSES[document.statut]
                            }`}
                            title={
                              document.est_doublon && document.doublon_de_document_id
                                ? `Doublon du document ${document.doublon_de_document_id}`
                                : undefined
                            }
                          >
                            {document.est_doublon
                              ? "Doublon"
                              : STATUS_LABELS[document.statut]}
                          </span>
                        </td>
                        <td className="px-4 py-3">{formatFileSize(document.taille_octets)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => navigate(`/documents/${document.id}`)}
                              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                            >
                              <FileSearch size={14} /> Vérifier
                            </button>
                            <button
                              type="button"
                              onClick={() => void openDocumentFile(document.id)}
                              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                            >
                              <ExternalLink size={14} /> Fichier
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleRetraiter(document)}
                              disabled={currentAction === `retry-${document.id}`}
                              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
                            >
                              <RefreshCw size={14} /> Retraiter
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDelete(document)}
                              disabled={currentAction === `delete-${document.id}`}
                              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                            >
                              <Trash2 size={14} /> Supprimer
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {!loading && filteredDocuments.length === 0 && (
                      <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">Aucun document.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <aside>
            <div
              onDragEnter={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={`rounded-xl border-2 border-dashed bg-white p-7 text-center shadow-sm transition ${
                dragging ? "border-green-500 bg-green-50" : "border-slate-300"
              }`}
            >
              <UploadCloud className="mx-auto text-green-600" size={46} />
              <h2 className="mt-4 font-bold text-slate-900">Import multiple</h2>
              <p className="mt-2 text-sm text-slate-500">
                Sélectionnez ou glissez plusieurs PDF, PNG ou JPEG en une seule fois.
                Taille maximale : 20 Mo par fichier.
              </p>

              {uploading && (
                <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-left text-xs text-slate-600">
                  <div className="flex items-center justify-between gap-3 font-semibold">
                    <span>{currentUploadName ?? "Préparation..."}</span>
                    <span>{uploadProgress.current}/{uploadProgress.total}</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-green-600 transition-all"
                      style={{
                        width: uploadProgress.total > 0
                          ? `${Math.round((uploadProgress.current / uploadProgress.total) * 100)}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>
              )}

              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                disabled={uploading}
                className="mt-5 rounded-lg border border-green-600 px-4 py-2 text-sm font-bold text-green-700 hover:bg-green-50 disabled:opacity-50"
              >
                {uploadButtonLabel}
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                multiple
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
