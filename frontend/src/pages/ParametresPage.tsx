import { useState, useEffect } from "react";
import { getCabinet, updateCabinet, getSystemInfo } from "../api/cabinetApi";
import { useAuth } from "../context/AuthContext";
import type { Cabinet, SystemInfo } from "../types/cabinet";

// Page Paramètres : formulaire d'édition du cabinet (admin uniquement,
// champs désactivés sinon) + bloc d'information système en lecture seule.
export function ParametresPage() {
  const { user } = useAuth();
  const [cabinet, setCabinet] = useState<Cabinet | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [form, setForm] = useState({ nom: "", ice: "", adresse: "", telephone: "", email: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const estAdmin = user?.role === "admin_cabinet" || user?.role === "super_admin";

  // Charge les données du cabinet et l'état système au montage de la page.
  useEffect(() => {
    getCabinet().then((data) => {
      setCabinet(data);
      setForm({
        nom: data.nom, ice: data.ice ?? "", adresse: data.adresse ?? "",
        telephone: data.telephone ?? "", email: data.email ?? "",
      });
    });
    getSystemInfo().then(setSystemInfo);
  }, []);

  // Envoie le formulaire modifié au backend, puis rafraîchit l'affichage.
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setMessage(null);
    try {
      const data = await updateCabinet(form);
      setCabinet(data);
      setMessage("Informations enregistrées.");
    } catch {
      setMessage("Erreur lors de l'enregistrement.");
    } finally {
      setIsSaving(false);
    }
  }

  if (!cabinet) return <div className="p-8 text-gray-500">Chargement...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-xl font-semibold">Paramètres</h1>

        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 space-y-4">
          <h2 className="font-medium text-sm mb-2">Informations du cabinet</h2>
          {message && <p className="text-sm text-green-700">{message}</p>}

          <div>
            <label className="block text-sm font-medium mb-1">Nom du cabinet</label>
            <input
              type="text" disabled={!estAdmin}
              value={form.nom}
              onChange={(e) => setForm({ ...form, nom: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">ICE</label>
              <input
                type="text" disabled={!estAdmin}
                value={form.ice}
                onChange={(e) => setForm({ ...form, ice: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Téléphone</label>
              <input
                type="text" disabled={!estAdmin}
                value={form.telephone}
                onChange={(e) => setForm({ ...form, telephone: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Adresse</label>
            <input
              type="text" disabled={!estAdmin}
              value={form.adresse}
              onChange={(e) => setForm({ ...form, adresse: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email" disabled={!estAdmin}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
            />
          </div>

          {estAdmin ? (
            <button type="submit" disabled={isSaving} className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded disabled:opacity-50">
              {isSaving ? "Enregistrement..." : "Enregistrer"}
            </button>
          ) : (
            <p className="text-xs text-gray-400">Seul un administrateur du cabinet peut modifier ces informations.</p>
          )}
        </form>

        {systemInfo && (
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="font-medium text-sm mb-3">Configuration IA (lecture seule)</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Mode actif</span>
                <span className="font-medium capitalize">{systemInfo.ai_provider === "cloud" ? "Cloud (Gemini/Groq)" : "Local (Ollama)"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Clé cloud configurée</span>
                <span className="font-medium">{systemInfo.gemini_configure ? "Oui" : "Non"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Modèle local</span>
                <span className="font-medium">{systemInfo.ollama_model}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}