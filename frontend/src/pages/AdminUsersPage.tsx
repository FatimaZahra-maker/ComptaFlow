import { useState, useEffect, useCallback } from "react";
import { listUsers, createUser, deactivateUser } from "../api/usersApi";
import type { UserAdmin, UserRole } from "../types/user";

const ROLES: { value: UserRole; label: string }[] = [
  { value: "admin_cabinet", label: "Admin Cabinet" },
  { value: "expert_comptable", label: "Expert-Comptable" },
  { value: "chef_mission", label: "Chef de Mission" },
  { value: "collaborateur", label: "Collaborateur" },
  { value: "assistant", label: "Assistant" },
];

const FORMULAIRE_VIDE = {
  email: "", nom: "", prenom: "", password: "", role: "collaborateur" as UserRole,
};

export function AdminUsersPage() {
  const [utilisateurs, setUtilisateurs] = useState<UserAdmin[]>([]);
  const [chargement, setChargement] = useState(true);
  const [formulaire, setFormulaire] = useState(FORMULAIRE_VIDE);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = useState(false);

  const rafraichirListe = useCallback(async () => {
    setChargement(true);
    try {
      setUtilisateurs(await listUsers());
    } catch (err: any) {
      setErreur(err.response?.data?.detail ?? "Impossible de charger les utilisateurs.");
    } finally {
      setChargement(false);
    }
  }, []);

  useEffect(() => {
    rafraichirListe();
  }, [rafraichirListe]);

  async function gererSoumission(evenement: React.FormEvent) {
    evenement.preventDefault();
    setErreur(null);
    setEnvoiEnCours(true);
    try {
      await createUser(formulaire);
      setFormulaire(FORMULAIRE_VIDE);
      await rafraichirListe();
    } catch (err: any) {
      setErreur(err.response?.data?.detail ?? "Erreur lors de la création.");
    } finally {
      setEnvoiEnCours(false);
    }
  }

  async function gererDesactivation(userId: string) {
    if (!window.confirm("Désactiver cet utilisateur ? Il ne pourra plus se connecter.")) return;
    try {
      await deactivateUser(userId);
      await rafraichirListe();
    } catch (err: any) {
      setErreur(err.response?.data?.detail ?? "Erreur lors de la désactivation.");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <h1 className="text-xl font-semibold">Gestion des utilisateurs</h1>

        <form onSubmit={gererSoumission} className="bg-white rounded-lg shadow-sm p-6 space-y-4">
          <h2 className="font-medium text-sm">Ajouter un utilisateur</h2>

          {erreur && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2">
              {erreur}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Prénom</label>
              <input
                type="text" required
                value={formulaire.prenom}
                onChange={(e) => setFormulaire({ ...formulaire, prenom: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Nom</label>
              <input
                type="text" required
                value={formulaire.nom}
                onChange={(e) => setFormulaire({ ...formulaire, nom: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email" required
                value={formulaire.email}
                onChange={(e) => setFormulaire({ ...formulaire, email: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Mot de passe</label>
              <input
                type="password" required minLength={8}
                value={formulaire.password}
                onChange={(e) => setFormulaire({ ...formulaire, password: e.target.value })}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium mb-1">Rôle</label>
              <select
                value={formulaire.role}
                onChange={(e) => setFormulaire({ ...formulaire, role: e.target.value as UserRole })}
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={envoiEnCours}
            className="bg-green-700 hover:bg-green-800 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded transition"
          >
            {envoiEnCours ? "Création..." : "Créer l'utilisateur"}
          </button>
        </form>

        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <h2 className="font-medium text-sm px-6 pt-6 pb-2">Utilisateurs du cabinet</h2>
          {chargement ? (
            <p className="text-sm text-gray-500 px-6 pb-6">Chargement...</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-t border-b bg-gray-50 text-left text-gray-500">
                  <th className="px-6 py-2">Nom</th>
                  <th className="px-6 py-2">Email</th>
                  <th className="px-6 py-2">Rôle</th>
                  <th className="px-6 py-2">Statut</th>
                  <th className="px-6 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {utilisateurs.map((u) => (
                  <tr key={u.id} className="border-b last:border-0">
                    <td className="px-6 py-3">{u.prenom} {u.nom}</td>
                    <td className="px-6 py-3 text-gray-600">{u.email}</td>
                    <td className="px-6 py-3 text-gray-600">
                      {ROLES.find((r) => r.value === u.role)?.label ?? u.role}
                    </td>
                    <td className="px-6 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                      }`}>
                        {u.is_active ? "Actif" : "Désactivé"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right">
                      {u.is_active && (
                        <button
                          onClick={() => gererDesactivation(u.id)}
                          className="text-red-600 hover:text-red-800 text-xs font-medium"
                        >
                          Désactiver
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}