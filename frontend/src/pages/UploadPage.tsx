import { useState, useEffect, useCallback } from "react";
import { uploadDocument, listDocuments } from "../api/documentsApi";
import type { Document } from "../types/document";

const STATUT_COLORS: Record<string, string> = {
  en_attente: "bg-gray-100 text-gray-700",
  en_traitement: "bg-yellow-100 text-yellow-700",
  traite: "bg-green-100 text-green-700",
  erreur: "bg-red-100 text-red-700",
};

export function UploadPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      // silencieux ici — le polling réessaiera dans 3s
    }
  }, []);

  // Polling toutes les 3s : c'est comme ça que tu vois le statut passer
  // de "en_attente" à "en_traitement" à "traite" sans recharger la page.
  useEffect(() => {
    refreshDocuments();
    const interval = setInterval(refreshDocuments, 3000);
    return () => clearInterval(interval);
  }, [refreshDocuments]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setIsUploading(true);
    try {
      await uploadDocument(file);
      await refreshDocuments();
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Erreur lors de l'upload.");
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-xl font-semibold mb-6">Importer un document</h1>

        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <label className="block">
            <span className="text-sm font-medium mb-2 block">Uploader un document</span>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
              disabled={isUploading}
              className="block w-full text-sm"
            />
          </label>
          {isUploading && <p className="text-sm text-blue-600 mt-2">Upload en cours...</p>}
          {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        </div>

        <div className="bg-white rounded-lg shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="p-3">Fichier</th>
                <th className="p-3">Statut</th>
                <th className="p-3">Catégorie</th>
                <th className="p-3">Date</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} className="border-b last:border-0">
                  <td className="p-3">{doc.nom_fichier_original}</td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs ${STATUT_COLORS[doc.statut]}`}>
                      {doc.statut}
                    </span>
                  </td>
                  <td className="p-3">{doc.categorie ?? "—"}</td>
                  <td className="p-3">{new Date(doc.created_at).toLocaleString("fr-FR")}</td>
                </tr>
              ))}
              {documents.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-6 text-center text-gray-400">
                    Aucun document pour l'instant.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}