import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getDocumentDetail } from "../api/documentDetailApi";
import { validateEntry, rejectEntry, updateEntry } from "../api/accountingApi";
import { listChronoDocuments } from "../api/chronosApi";
import { listEntreprises } from "../api/entreprisesApi";
import { getDocumentFileUrl } from "../api/documentsApi";
import type { DocumentDetail } from "../types/documentDetail";
import type { DocumentChrono } from "../types/chrono";
import type { Entreprise } from "../types/entreprise";

const STATUT_LABELS: Record<string, string> = {
  en_attente: "En attente",
  en_traitement: "En traitement",
  traite: "Traité",
  valide: "Validé",
  erreur: "Erreur",
};

const STATUT_COLORS: Record<string, string> = {
  en_attente: "bg-gray-100 text-gray-700",
  en_traitement: "bg-yellow-100 text-yellow-700",
  traite: "bg-blue-100 text-blue-700",
  valide: "bg-green-100 text-green-700",
  erreur: "bg-red-100 text-red-700",
};

const VALIDATION_LABELS: Record<string, string> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validé",
  rejete: "Rejeté",
};

const CHAMP_LABELS: Record<string, string> = {
  date: "Date",
  numero_facture: "Numéro facture",
  ice_fournisseur: "ICE Fournisseur",
  nom_fournisseur: "Nom fournisseur",
  ice_client: "ICE Client",
  nom_client: "Nom client",
  if_client: "IF Client",
  if_fournisseur: "IF Fournisseur",
  rc_fournisseur: "RC Fournisseur",
  rc_client: "RC Client",
  ht: "HT",
  tva: "TVA",
  ttc: "TTC",
  categorie: "Catégorie",
  statut: "Statut",
};

const CHAMP_ORDRE = [
  "date", "numero_facture", "ice_fournisseur", "nom_fournisseur",
  "ice_client", "nom_client", "if_client", "rc_fournisseur",
  "ht", "tva", "ttc", "categorie", "statut",
];

interface VerificationItem {
  label: string;
  ok: boolean | null;
}

function calculerVerifications(detail: DocumentDetail): VerificationItem[] {
  const donnees = (detail.donnees_extraites ?? {}) as Record<string, unknown>;
  const iceFournisseur = donnees["ice_fournisseur"];
  const iceClient = donnees["ice_client"];

  return [
    {
      label: "ICE Fournisseur présent",
      ok: iceFournisseur ? String(iceFournisseur).replace(/\s/g, "").length >= 9 : null,
    },
    {
      label: "ICE Client présent",
      ok: iceClient ? String(iceClient).replace(/\s/g, "").length >= 9 : null,
    },
    {
      label: "Montants HT/TVA/TTC cohérents",
      ok: detail.ecriture
        ? Math.abs(
            parseFloat(detail.ecriture.montant_ht) +
              parseFloat(detail.ecriture.montant_tva) -
              parseFloat(detail.ecriture.montant_ttc)
          ) < 0.05
        : null,
    },
    {
      label: "Pas de doublon détecté",
      ok: detail.ecriture ? !detail.ecriture.anomalie_detectee : null,
    },
    {
      label: "Entreprise identifiée",
      ok: detail.entreprise_id !== null,
    },
  ];
}

function construireLignesEcriture(detail: DocumentDetail) {
  const e = detail.ecriture;
  if (!e) return [];
  const estVente = e.type_ecriture?.toLowerCase().includes("vente");
  const tiers = e.tiers ?? "Tiers";

  if (estVente) {
    return [
      { compte: "3421", libelle: `Client ${tiers}`, debit: e.montant_ttc, credit: null },
      { compte: "7111", libelle: "Ventes de marchandises", debit: null, credit: e.montant_ht },
      { compte: "4455", libelle: "État — TVA facturée", debit: null, credit: e.montant_tva },
    ];
  }
  return [
    { compte: "6111", libelle: "Achats marchandises", debit: e.montant_ht, credit: null },
    { compte: "34552", libelle: "TVA déductible sur achats", debit: e.montant_tva, credit: null },
    { compte: "4411", libelle: `Fournisseur ${tiers}`, debit: null, credit: e.montant_ttc },
  ];
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [chronoSiblings, setChronoSiblings] = useState<DocumentChrono[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [rechercheFooter, setRechercheFooter] = useState("");
  const [filtreStatutFooter, setFiltreStatutFooter] = useState<string>("");
  const [commentaireDraft, setCommentaireDraft] = useState("");

  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    tiers: "", numero_piece: "", date_piece: "", montant_ht: "", montant_tva: "", montant_ttc: "",
  });

  const refresh = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getDocumentDetail(id);
      setDetail(data);
      setError(null);
    } catch {
      setError("Impossible de charger ce document.");
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    listEntreprises().then(setEntreprises);
  }, []);

  useEffect(() => {
    if (!detail || !detail.entreprise_id || !detail.annee || !detail.mois || !detail.categorie) {
      setChronoSiblings([]);
      return;
    }
    listChronoDocuments({
      entreprise_id: detail.entreprise_id,
      categorie: detail.categorie,
      annee: detail.annee,
      mois: detail.mois,
    }).then(setChronoSiblings);
  }, [detail?.entreprise_id, detail?.annee, detail?.mois, detail?.categorie]);

  const entrepriseNom = useMemo(
    () => entreprises.find((e) => e.id === detail?.entreprise_id)?.nom ?? null,
    [entreprises, detail?.entreprise_id]
  );

  const verifications = useMemo(() => (detail ? calculerVerifications(detail) : []), [detail]);
  const lignesEcriture = useMemo(() => (detail ? construireLignesEcriture(detail) : []), [detail]);

  const scoreCompletude = useMemo(() => {
    if (!detail?.donnees_extraites) return null;
    const valeurs = Object.values(detail.donnees_extraites);
    if (valeurs.length === 0) return null;
    const remplis = valeurs.filter((v) => v !== null && v !== undefined && v !== "").length;
    return Math.round((remplis / valeurs.length) * 100);
  }, [detail?.donnees_extraites]);

  function ouvrirCorrection() {
    if (!detail?.ecriture) return;
    setEditForm({
      tiers: detail.ecriture.tiers ?? "",
      numero_piece: detail.ecriture.numero_piece ?? "",
      date_piece: detail.ecriture.date_piece ?? "",
      montant_ht: detail.ecriture.montant_ht,
      montant_tva: detail.ecriture.montant_tva,
      montant_ttc: detail.ecriture.montant_ttc,
    });
    setIsEditing(true);
  }

  async function enregistrerCorrection() {
    if (!detail?.ecriture) return;
    setIsProcessing(true);
    try {
      await updateEntry(detail.ecriture.id, editForm);
      setIsEditing(false);
      await refresh();
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleValidate() {
    if (!detail?.ecriture) return;
    setIsProcessing(true);
    try {
      await validateEntry(detail.ecriture.id);
      await refresh();
    } finally {
      setIsProcessing(false);
    }
  }

  async function handleReject() {
    if (!detail?.ecriture) return;
    setIsProcessing(true);
    try {
      await rejectEntry(detail.ecriture.id);
      await refresh();
    } finally {
      setIsProcessing(false);
    }
  }

  const siblingsFiltres = chronoSiblings.filter((s) => {
    if (filtreStatutFooter && s.statut_validation !== filtreStatutFooter) return false;
    if (rechercheFooter && !s.nom_fichier_original.toLowerCase().includes(rechercheFooter.toLowerCase())) return false;
    return true;
  });

  if (isLoading) return <div className="p-8 text-gray-500">Chargement...</div>;

  if (error || !detail) {
    return (
      <div className="p-8">
        <p className="text-red-600 mb-4">{error ?? "Document introuvable."}</p>
        <button onClick={() => navigate("/chronos")} className="text-green-700 text-sm">
          ← Retour aux chronos
        </button>
      </div>
    );
  }

  const isImage = detail.mime_type?.startsWith("image/");
  const isPdf = detail.mime_type === "application/pdf";
  const fileUrl = getDocumentFileUrl(detail.id);
  const heuresDepuisImport = (Date.now() - new Date(detail.created_at).getTime()) / 3_600_000;
  const estNouveau = heuresDepuisImport < 48;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-[1600px] mx-auto">
        <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
          <button onClick={() => navigate("/chronos")} className="hover:text-green-700 hover:underline">
            Documents
          </button>
          <span>›</span>
          <span className="text-gray-600">{detail.nom_fichier_original}</span>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <h1 className="text-lg font-semibold">{detail.nom_fichier_original}</h1>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_COLORS[detail.statut]}`}>
            {STATUT_LABELS[detail.statut]}
          </span>
          {estNouveau && (
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-600">
              Nouveau
            </span>
          )}
          {entrepriseNom && <span className="text-sm text-gray-400">· {entrepriseNom}</span>}
        </div>

        <div className="grid grid-cols-12 gap-4 mb-4">
          <div className="col-span-12 lg:col-span-5 bg-white rounded-lg shadow-sm overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-3 py-2 border-b bg-gray-50 text-xs text-gray-500">
              <span>{detail.mime_type ?? "—"}</span>
              <div className="flex items-center gap-2">
                <button onClick={() => setZoom((z) => Math.max(40, z - 20))} className="px-1.5 hover:bg-gray-200 rounded" title="Zoom arrière">
                  −
                </button>
                <span className="w-10 text-center">{zoom}%</span>
                <button onClick={() => setZoom((z) => Math.min(300, z + 20))} className="px-1.5 hover:bg-gray-200 rounded" title="Zoom avant">
                  +
                </button>
                <a href={fileUrl} target="_blank" rel="noreferrer" className="text-green-700 hover:underline ml-2">
                  Ouvrir ↗
                </a>
              </div>
            </div>
            <div className="flex-1 min-h-[520px] bg-gray-100 overflow-auto flex items-start justify-center p-3">
              {isImage && (
                <img src={fileUrl} alt={detail.nom_fichier_original} style={{ width: `${zoom}%` }} className="max-w-none shadow" />
              )}
              {isPdf && (
                <iframe src={`${fileUrl}#toolbar=0`} title={detail.nom_fichier_original} className="w-full h-[520px] border-0" />
              )}
              {!isImage && !isPdf && (
                <div className="text-sm text-gray-400 p-8 text-center">
                  Aperçu non disponible pour ce type de fichier.
                  <br />
                  <a href={fileUrl} target="_blank" rel="noreferrer" className="text-green-700 hover:underline">
                    Ouvrir le fichier original ↗
                  </a>
                </div>
              )}
            </div>
          </div>

          <div className="col-span-12 lg:col-span-3 space-y-4">
            <div className="bg-white rounded-lg shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium">Informations extraites (IA)</h2>
              </div>
              {scoreCompletude !== null && (
                <div className="mb-3">
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Score global</span>
                    <span className="font-medium text-gray-600">{scoreCompletude}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full" style={{ width: `${scoreCompletude}%` }} />
                  </div>
                </div>
              )}
              <div className="space-y-2 text-sm">
                {detail.donnees_extraites ? (
                  <>
                    {CHAMP_ORDRE.filter((k) => k in (detail.donnees_extraites as object)).map((cle) => {
                      const valeur = (detail.donnees_extraites as Record<string, unknown>)[cle];
                      const affichage =
                        valeur === null || valeur === undefined || valeur === ""
                          ? "—"
                          : typeof valeur === "object"
                          ? JSON.stringify(valeur)
                          : String(valeur);
                      return (
                        <div key={cle} className="flex justify-between gap-2">
                          <span className="text-gray-400">{CHAMP_LABELS[cle] ?? cle}</span>
                          <span className="font-medium text-right break-all">{affichage}</span>
                        </div>
                      );
                    })}
                    {Object.entries(detail.donnees_extraites)
                      .filter(([k]) => !CHAMP_ORDRE.includes(k))
                      .map(([cle, valeur]) => {
                        const affichage =
                          valeur === null || valeur === undefined || valeur === ""
                            ? "—"
                            : typeof valeur === "object"
                            ? JSON.stringify(valeur)
                            : String(valeur);
                        return (
                          <div key={cle} className="flex justify-between gap-2">
                            <span className="text-gray-400">{cle}</span>
                            <span className="font-medium text-right break-all">{affichage}</span>
                          </div>
                        );
                      })}
                  </>
                ) : (
                  <p className="text-gray-400">Pas encore de données extraites.</p>
                )}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm p-4">
              <h2 className="text-sm font-medium mb-3">Vérifications</h2>
              <div className="space-y-2 text-sm">
                {verifications.map((v) => (
                  <div key={v.label} className="flex items-center justify-between">
                    <span className={v.ok === false ? "text-red-600" : "text-gray-600"}>{v.label}</span>
                    <span>
                      {v.ok === null ? (
                        <span className="text-gray-300">—</span>
                      ) : v.ok ? (
                        <span className="text-green-600">✓</span>
                      ) : (
                        <span className="text-red-600">✕</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              {detail.ecriture?.anomalie_details && (
                <p className="text-xs text-orange-600 mt-3 bg-orange-50 rounded p-2">{detail.ecriture.anomalie_details}</p>
              )}
            </div>
          </div>

          <div className="col-span-12 lg:col-span-4 space-y-4">
            <div className="bg-white rounded-lg shadow-sm p-4">
              <h2 className="text-sm font-medium mb-3">Écriture comptable proposée</h2>
              {lignesEcriture.length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-400 border-b">
                      <th className="pb-1.5">Compte</th>
                      <th className="pb-1.5">Libellé</th>
                      <th className="pb-1.5 text-right">Débit</th>
                      <th className="pb-1.5 text-right">Crédit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lignesEcriture.map((ligne) => (
                      <tr key={ligne.compte} className="border-b last:border-0">
                        <td className="py-1.5">{ligne.compte}</td>
                        <td className="py-1.5">{ligne.libelle}</td>
                        <td className="py-1.5 text-right">{ligne.debit ? parseFloat(ligne.debit).toFixed(2) : "-"}</td>
                        <td className="py-1.5 text-right">{ligne.credit ? parseFloat(ligne.credit).toFixed(2) : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-gray-400">Pas encore d'écriture générée pour ce document.</p>
              )}
            </div>

            <div className="bg-white rounded-lg shadow-sm p-4">
              <h2 className="text-sm font-medium mb-2">Commentaires</h2>
              <input
                type="text"
                value={commentaireDraft}
                onChange={(e) => setCommentaireDraft(e.target.value)}
                placeholder="Ajouter un commentaire..."
                disabled
                title="Bientôt disponible — nécessite une table de commentaires côté backend"
                className="w-full border rounded px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed"
              />
            </div>

            <div className="bg-white rounded-lg shadow-sm p-4">
              <h2 className="text-sm font-medium mb-2">Historique</h2>
              <ul className="text-sm space-y-1.5">
                <li className="flex justify-between">
                  <span className="text-gray-600">Document importé</span>
                  <span className="text-gray-400 text-xs">{new Date(detail.created_at).toLocaleDateString("fr-FR")}</span>
                </li>
                {detail.statut !== "en_attente" && (
                  <li className="flex justify-between">
                    <span className="text-gray-600">OCR / extraction IA effectués</span>
                    <span className="text-gray-400 text-xs">—</span>
                  </li>
                )}
                {detail.ecriture && (
                  <li className="flex justify-between">
                    <span className="text-gray-600">Écriture {VALIDATION_LABELS[detail.ecriture.statut_validation]}</span>
                    <span className="text-gray-400 text-xs">—</span>
                  </li>
                )}
              </ul>
            </div>

            {detail.ecriture && (
              <div className="bg-white rounded-lg shadow-sm p-4 flex gap-2 flex-wrap">
                <button
                  onClick={handleReject}
                  disabled={isProcessing || detail.ecriture.statut_validation === "rejete"}
                  className="px-4 py-2 rounded text-sm font-medium bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-40"
                >
                  Rejeter
                </button>
                <button
                  onClick={ouvrirCorrection}
                  className="px-4 py-2 rounded text-sm font-medium bg-yellow-50 text-yellow-700 hover:bg-yellow-100"
                >
                  Corriger
                </button>
                <button
                  onClick={handleValidate}
                  disabled={isProcessing || detail.ecriture.statut_validation === "valide"}
                  className="px-4 py-2 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-40"
                >
                  Valider
                </button>
                <a
                  href={`http://localhost:8000/export/topaze/${detail.ecriture.id}?token=${localStorage.getItem("comptaflow_token")}`}
                  className="px-4 py-2 rounded text-sm font-medium bg-green-50 text-green-700 hover:bg-green-100 ml-auto text-center"
                >
                  Exporter Topaze
                </a>
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          <div className="col-span-12 lg:col-span-8 bg-white rounded-lg shadow-sm p-4">
            <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
              <span className="font-medium text-gray-600">Chronos</span>
              {entrepriseNom && <span>· {entrepriseNom}</span>}
              {detail.annee && <span>· {detail.annee}</span>}
              {detail.categorie && <span className="capitalize">· {detail.categorie}</span>}
            </div>
            <div className="flex gap-3 overflow-x-auto pb-1">
              {siblingsFiltres.length === 0 && (
                <p className="text-sm text-gray-400 py-4">Aucun document voisin pour ce classement.</p>
              )}
              {siblingsFiltres.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  className={`shrink-0 w-36 text-left border rounded-lg p-2.5 hover:border-green-300 transition ${
                    doc.id === detail.id ? "border-green-400 bg-green-50" : "border-gray-200"
                  }`}
                >
                  <p className="text-xs font-medium truncate">{doc.nom_fichier_original}</p>
                  <p className="text-[11px] text-gray-400">
                    {doc.date_piece ? new Date(doc.date_piece).toLocaleDateString("fr-FR") : "—"}
                  </p>
                  <p className="text-[11px] font-medium">
                    {doc.montant_ttc ? `${parseFloat(doc.montant_ttc).toFixed(2)} DH` : "—"}
                  </p>
                  {doc.statut_validation && (
                    <span
                      className={`inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded ${
                        doc.statut_validation === "valide" ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"
                      }`}
                    >
                      {VALIDATION_LABELS[doc.statut_validation]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="col-span-12 lg:col-span-4 bg-white rounded-lg shadow-sm p-4">
            <h2 className="text-sm font-medium mb-2">Recherche rapide</h2>
            <input
              type="text"
              value={rechercheFooter}
              onChange={(e) => setRechercheFooter(e.target.value)}
              placeholder="Rechercher..."
              className="w-full border rounded px-3 py-2 text-sm mb-2 focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
            />
            <select
              value={filtreStatutFooter}
              onChange={(e) => setFiltreStatutFooter(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            >
              <option value="">Tous les statuts</option>
              <option value="brouillon">Brouillon</option>
              <option value="a_verifier">À vérifier</option>
              <option value="valide">Validé</option>
              <option value="rejete">Rejeté</option>
            </select>
          </div>
        </div>

        {isEditing && detail.ecriture && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
              <h2 className="font-medium mb-4">Corriger l'écriture</h2>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Tiers</label>
                  <input
                    type="text"
                    value={editForm.tiers}
                    onChange={(e) => setEditForm({ ...editForm, tiers: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">N° pièce</label>
                  <input
                    type="text"
                    value={editForm.numero_piece}
                    onChange={(e) => setEditForm({ ...editForm, numero_piece: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Date pièce</label>
                  <input
                    type="date"
                    value={editForm.date_piece}
                    onChange={(e) => setEditForm({ ...editForm, date_piece: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">HT</label>
                    <input
                      type="number" step="0.01"
                      value={editForm.montant_ht}
                      onChange={(e) => setEditForm({ ...editForm, montant_ht: e.target.value })}
                      className="w-full border rounded px-2 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">TVA</label>
                    <input
                      type="number" step="0.01"
                      value={editForm.montant_tva}
                      onChange={(e) => setEditForm({ ...editForm, montant_tva: e.target.value })}
                      className="w-full border rounded px-2 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">TTC</label>
                    <input
                      type="number" step="0.01"
                      value={editForm.montant_ttc}
                      onChange={(e) => setEditForm({ ...editForm, montant_ttc: e.target.value })}
                      className="w-full border rounded px-2 py-2 text-sm"
                    />
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-5">
                <button onClick={() => setIsEditing(false)} className="px-4 py-2 text-sm text-gray-500">
                  Annuler
                </button>
                <button
                  onClick={enregistrerCorrection}
                  disabled={isProcessing}
                  className="px-4 py-2 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                >
                  Enregistrer
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}