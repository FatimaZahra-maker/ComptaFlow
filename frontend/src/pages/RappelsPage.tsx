import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { listEntreprises } from "../api/entreprisesApi";
import { listTaches, createTache, terminerTache, deleteTache } from "../api/tachesApi";
// AJOUTÉ : appel des alertes automatiques (non-saisies + entreprises en retard)
import { getAlertesRappels } from "../api/rappelsApi";
// AJOUTÉ : pour marquer une écriture "saisie" directement depuis cette page
import { toggleSaisieTopaze } from "../api/accountingApi";
import type { Entreprise } from "../types/entreprise";
import type { Tache, PrioriteTache, RecurrenceTache } from "../types/tache";
import type { AlertesRappels } from "../types/rappel";

const STATUT_LABELS: Record<string, string> = {
  a_faire: "À faire", en_cours: "En cours", terminee: "Terminée",
};

const PRIORITE_COLORS: Record<string, string> = {
  basse: "bg-gray-100 text-gray-600",
  normale: "bg-blue-50 text-blue-700",
  haute: "bg-red-50 text-red-700",
};

const RECURRENCE_LABELS: Record<string, string> = {
  aucune: "Aucune", mensuelle: "Mensuelle", trimestrielle: "Trimestrielle", annuelle: "Annuelle",
};

const FORMULAIRE_VIDE = {
  entreprise_id: "", titre: "", description: "", date_echeance: "",
  priorite: "normale" as PrioriteTache, recurrence: "aucune" as RecurrenceTache,
};

export function RappelsPage() {
  const navigate = useNavigate();

  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [taches, setTaches] = useState<Tache[]>([]);
  const [filtreEntreprise, setFiltreEntreprise] = useState("");
  const [filtreStatut, setFiltreStatut] = useState("");
  const [seulementEnRetard, setSeulementEnRetard] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [formulaireOuvert, setFormulaireOuvert] = useState(false);
  const [formulaire, setFormulaire] = useState(FORMULAIRE_VIDE);

  // --- AJOUTÉ : état des alertes automatiques ---
  const [alertes, setAlertes] = useState<AlertesRappels | null>(null);
  const [isLoadingAlertes, setIsLoadingAlertes] = useState(true);

  useEffect(() => {
    listEntreprises().then(setEntreprises);
  }, []);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listTaches({
        entreprise_id: filtreEntreprise || undefined,
        statut: filtreStatut || undefined,
        seulement_en_retard: seulementEnRetard || undefined,
      });
      setTaches(data);
    } finally {
      setIsLoading(false);
    }
  }, [filtreEntreprise, filtreStatut, seulementEnRetard]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // AJOUTÉ : chargement séparé des alertes automatiques (indépendant des
  // filtres de tâches manuelles, donc effet séparé).
  const refreshAlertes = useCallback(async () => {
    setIsLoadingAlertes(true);
    try {
      const data = await getAlertesRappels();
      setAlertes(data);
    } catch (error) {
      console.error("Erreur lors du chargement des alertes automatiques :", error);
      setAlertes(null);
    } finally {
      setIsLoadingAlertes(false);
    }
  }, []);

  useEffect(() => {
    refreshAlertes();
  }, [refreshAlertes]);

  async function handleCreer(e: React.FormEvent) {
    e.preventDefault();
    await createTache({
      entreprise_id: formulaire.entreprise_id || undefined,
      titre: formulaire.titre,
      description: formulaire.description || undefined,
      date_echeance: formulaire.date_echeance,
      priorite: formulaire.priorite,
      recurrence: formulaire.recurrence,
    });
    setFormulaire(FORMULAIRE_VIDE);
    setFormulaireOuvert(false);
    await refresh();
  }

  async function handleTerminer(id: string) {
    await terminerTache(id);
    await refresh();
  }

  async function handleSupprimer(id: string) {
    if (!window.confirm("Supprimer cette tâche ?")) return;
    await deleteTache(id);
    await refresh();
  }

  // AJOUTÉ : marquer une écriture "saisie dans Topaze" directement depuis
  // cette page, sans avoir à aller sur la page Écritures.
  async function handleMarquerSaisie(id: string) {
    await toggleSaisieTopaze(id);
    await refreshAlertes();
  }

  // AJOUTÉ : pré-remplit le formulaire de tâche manuelle avec l'entreprise
  // en retard, pour créer rapidement une relance ("Relancer X").
  function handleCreerRelance(entrepriseId: string, entrepriseNom: string) {
    const dansUneSemaine = new Date();
    dansUneSemaine.setDate(dansUneSemaine.getDate() + 7);
    setFormulaire({
      ...FORMULAIRE_VIDE,
      entreprise_id: entrepriseId,
      titre: `Relancer ${entrepriseNom} — envoi de facture en retard`,
      date_echeance: dansUneSemaine.toISOString().slice(0, 10),
    });
    setFormulaireOuvert(true);
  }

  function formatMontant(valeur: string): string {
    const parsed = parseFloat(valeur);
    return isNaN(parsed) ? "—" : `${parsed.toFixed(2)} MAD`;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold">Rappels & Tâches</h1>
            <p className="text-sm text-gray-500">{taches.length} tâche(s)</p>
          </div>
          <button
            onClick={() => setFormulaireOuvert((o) => !o)}
            className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded"
          >
            {formulaireOuvert ? "Annuler" : "+ Nouvelle tâche"}
          </button>
        </div>

        {formulaireOuvert && (
          <form onSubmit={handleCreer} className="bg-white rounded-lg shadow-sm p-5 mb-6 space-y-3">
            <input
              type="text" required placeholder="Titre de la tâche"
              value={formulaire.titre}
              onChange={(e) => setFormulaire({ ...formulaire, titre: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Description (optionnel)"
              value={formulaire.description}
              onChange={(e) => setFormulaire({ ...formulaire, description: e.target.value })}
              className="w-full border rounded px-3 py-2 text-sm"
              rows={2}
            />
            <div className="grid grid-cols-2 gap-3">
              <select
                value={formulaire.entreprise_id}
                onChange={(e) => setFormulaire({ ...formulaire, entreprise_id: e.target.value })}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="">Cabinet (général)</option>
                {entreprises.map((ent) => (
                  <option key={ent.id} value={ent.id}>{ent.nom}</option>
                ))}
              </select>
              <input
                type="date" required
                value={formulaire.date_echeance}
                onChange={(e) => setFormulaire({ ...formulaire, date_echeance: e.target.value })}
                className="border rounded px-3 py-2 text-sm"
              />
              <select
                value={formulaire.priorite}
                onChange={(e) => setFormulaire({ ...formulaire, priorite: e.target.value as PrioriteTache })}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="basse">Priorité basse</option>
                <option value="normale">Priorité normale</option>
                <option value="haute">Priorité haute</option>
              </select>
              <select
                value={formulaire.recurrence}
                onChange={(e) => setFormulaire({ ...formulaire, recurrence: e.target.value as RecurrenceTache })}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="aucune">Pas de récurrence</option>
                <option value="mensuelle">Récurrence mensuelle</option>
                <option value="trimestrielle">Récurrence trimestrielle</option>
                <option value="annuelle">Récurrence annuelle</option>
              </select>
            </div>
            <button type="submit" className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded">
              Créer la tâche
            </button>
          </form>
        )}

        {/* ============ AJOUTÉ : SECTION 1 — ENTREPRISES EN RETARD ============ */}
        <div className="bg-white rounded-lg shadow-sm mb-6">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">
              🏢 Entreprises en retard d'envoi
              {alertes && ` (${alertes.entreprises_en_retard.length})`}
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Basé sur le délai habituel entre les 2 premiers documents reçus de chaque entreprise.
            </p>
          </div>
          {isLoadingAlertes && <p className="p-4 text-sm text-gray-400">Chargement...</p>}
          {!isLoadingAlertes && alertes?.entreprises_en_retard.length === 0 && (
            <p className="p-4 text-sm text-gray-400">Aucune entreprise en retard actuellement.</p>
          )}
          {!isLoadingAlertes && alertes?.entreprises_en_retard.map((ent) => (
            <div key={ent.entreprise_id} className="px-4 py-3 border-b last:border-0 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{ent.entreprise_nom}</p>
                <p className="text-xs text-gray-500">
                  Dernier envoi il y a {Math.round(ent.jours_depuis_dernier_upload)} jour(s)
                  {" "}(habituellement tous les {Math.round(ent.delai_reference_jours)} jour(s)
                  {" "}· {Math.round(ent.jours_de_retard)} jour(s) de retard)
                </p>
              </div>
              <button
                onClick={() => handleCreerRelance(ent.entreprise_id, ent.entreprise_nom)}
                className="text-xs shrink-0 px-3 py-1.5 rounded border border-orange-300 text-orange-700 hover:bg-orange-50 font-medium"
              >
                Créer une relance
              </button>
            </div>
          ))}
        </div>

        {/* ============ AJOUTÉ : SECTION 2 — DOCUMENTS NON SAISIS ============ */}
        <div className="bg-white rounded-lg shadow-sm mb-6">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold">
              📄 Écritures validées non saisies dans Topaze
              {alertes && ` (${alertes.non_saisies.length})`}
            </h2>
          </div>
          {isLoadingAlertes && <p className="p-4 text-sm text-gray-400">Chargement...</p>}
          {!isLoadingAlertes && alertes?.non_saisies.length === 0 && (
            <p className="p-4 text-sm text-gray-400">Tout est à jour, rien à ressaisir.</p>
          )}
          {!isLoadingAlertes && alertes?.non_saisies.map((item) => (
            <div key={item.id} className="px-4 py-3 border-b last:border-0 flex items-center justify-between gap-3">
              <button
                onClick={() => navigate(`/documents/${item.document_id}`)}
                className="text-left flex-1 min-w-0"
                title="Voir le document"
              >
                <p className="text-sm font-medium truncate">
                  {item.tiers ?? "Tiers inconnu"}
                  {item.numero_piece && ` · ${item.numero_piece}`}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {item.entreprise_nom} · {item.nom_fichier_document} · {formatMontant(item.montant_ttc)}
                </p>
              </button>
              <button
                onClick={() => handleMarquerSaisie(item.id)}
                className="text-xs shrink-0 px-3 py-1.5 rounded border border-green-300 text-green-700 hover:bg-green-50 font-medium"
              >
                ✓ Marquer saisie
              </button>
            </div>
          ))}
        </div>

        {/* ============ SECTION EXISTANTE : TÂCHES MANUELLES ============ */}
        <h2 className="text-sm font-semibold mb-2 px-1">📋 Tâches manuelles</h2>

        <div className="bg-white rounded-lg shadow-sm p-4 mb-4 flex flex-wrap gap-3">
          <select value={filtreEntreprise} onChange={(e) => setFiltreEntreprise(e.target.value)} className="border rounded px-3 py-2 text-sm">
            <option value="">Toutes les entreprises</option>
            {entreprises.map((ent) => (
              <option key={ent.id} value={ent.id}>{ent.nom}</option>
            ))}
          </select>
          <select value={filtreStatut} onChange={(e) => setFiltreStatut(e.target.value)} className="border rounded px-3 py-2 text-sm">
            <option value="">Tous les statuts</option>
            <option value="a_faire">À faire</option>
            <option value="en_cours">En cours</option>
            <option value="terminee">Terminée</option>
          </select>
          <label className="flex items-center gap-2 text-sm px-2">
            <input type="checkbox" checked={seulementEnRetard} onChange={(e) => setSeulementEnRetard(e.target.checked)} />
            En retard seulement
          </label>
        </div>

        <div className="bg-white rounded-lg shadow-sm divide-y">
          {isLoading && <p className="p-6 text-center text-gray-400 text-sm">Chargement...</p>}
          {!isLoading && taches.length === 0 && <p className="p-6 text-center text-gray-400 text-sm">Aucune tâche pour ces filtres.</p>}
          {!isLoading && taches.map((t) => (
            <div key={t.id} className={`p-4 flex items-start gap-3 ${t.est_en_retard ? "bg-red-50" : ""}`}>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{t.titre}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${PRIORITE_COLORS[t.priorite]}`}>{t.priorite}</span>
                  {t.recurrence !== "aucune" && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-700">
                      🔁 {RECURRENCE_LABELS[t.recurrence]}
                    </span>
                  )}
                  {t.est_en_retard && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">En retard</span>
                  )}
                </div>
                {t.description && <p className="text-sm text-gray-500 mb-1">{t.description}</p>}
                <p className="text-xs text-gray-400">
                  Échéance {new Date(t.date_echeance).toLocaleDateString("fr-FR")}
                  {t.entreprise_nom && ` · ${t.entreprise_nom}`}
                  {!t.entreprise_nom && " · Cabinet"}
                  {" · "}{STATUT_LABELS[t.statut]}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                {t.statut !== "terminee" && (
                  <button onClick={() => handleTerminer(t.id)} className="text-xs text-green-700 hover:text-green-900 font-medium">
                    ✓ Terminer
                  </button>
                )}
                <button onClick={() => handleSupprimer(t.id)} className="text-xs text-red-600 hover:text-red-800 font-medium">
                  Supprimer
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}