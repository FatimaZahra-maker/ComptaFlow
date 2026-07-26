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

// --- CONSTANTES DE CONFIGURATION ---
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

// --- INTERFACES UTILES ---
interface VerificationItem {
  label: string;
  ok: boolean | null;
}

// --- FONCTIONS UTILITAIRES ---
/**
 * Calcule les vérifications automatiques (ICE, montants, doublons) basées sur les données extraites.
 */
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
      ok: detail.ecriture && detail.ecriture.montant_ttc
        ? Math.abs(
            parseFloat(detail.ecriture.montant_ht || "0") +
              parseFloat(detail.ecriture.montant_tva || "0") -
              parseFloat(detail.ecriture.montant_ttc || "0")
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

/**
 * Construit les lignes d'écritures comptables (débit/crédit) selon qu'il s'agit d'une vente ou d'un achat.
 */
function construireLignesEcriture(detail: DocumentDetail) {
  const e = detail.ecriture;
  if (!e) return [];
  const estVente = e.type_ecriture?.toLowerCase().includes("vente");
  const tiers = e.tiers ?? "Tiers";
  
  const ht = e.montant_ht || null;
  const tva = e.montant_tva || null;
  const ttc = e.montant_ttc || null;

  if (estVente) {
    return [
      { compte: "3421", libelle: `Client ${tiers}`, debit: ttc, credit: null },
      { compte: "7111", libelle: "Ventes de marchandises", debit: null, credit: ht },
      { compte: "4455", libelle: "État — TVA facturée", debit: null, credit: tva },
    ];
  }
  return [
    { compte: "6111", libelle: "Achats marchandises", debit: ht, credit: null },
    { compte: "34552", libelle: "TVA déductible sur achats", debit: tva, credit: null },
    { compte: "4411", libelle: `Fournisseur ${tiers}`, debit: null, credit: ttc },
  ];
}

// --- COMPOSANT PRINCIPAL ---
export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // --- ÉTATS ---
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

  // --- EFFETS ET RÉCUPÉRATION DE DONNÉES ---
  const refresh = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
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

  // --- MÉMOÏSATIONS ---
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

  // --- ACTIONS (ÉDITION, VALIDATION, REJET) ---
  function ouvrirCorrection() {
    if (!detail?.ecriture) return;
    setEditForm({
      tiers: detail.ecriture.tiers ?? "",
      numero_piece: detail.ecriture.numero_piece ?? "",
      date_piece: detail.ecriture.date_piece ?? "",
      montant_ht: detail.ecriture.montant_ht ?? "",
      montant_tva: detail.ecriture.montant_tva ?? "",
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

  // --- RENDUS CONDITIONNELS ---
  if (isLoading) return <div className="p-8 text-gray-500 animate-pulse">Chargement en cours...</div>;

  if (error || !detail) {
    return (
      <div className="p-8 flex flex-col items-start gap-4">
        <p className="text-red-600 font-medium">{error ?? "Document introuvable."}</p>
        <button onClick={() => navigate("/chronos")} className="px-4 py-2 bg-green-50 text-green-700 rounded hover:bg-green-100 text-sm font-medium transition-colors">
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
    <div className="min-h-screen bg-gray-50 p-6 font-sans">
      <div className="max-w-[1600px] mx-auto">
        
        {/* FIL D'ARIANE */}
        <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
          <button onClick={() => navigate("/chronos")} className="hover:text-green-700 hover:underline transition-colors">
            Documents
          </button>
          <span>›</span>
          <span className="text-gray-600 truncate max-w-xs">{detail.nom_fichier_original}</span>
        </div>

        {/* EN-TÊTE DU DOCUMENT */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <h1 className="text-xl font-bold text-slate-800">{detail.nom_fichier_original}</h1>
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${STATUT_COLORS[detail.statut]}`}>
            {STATUT_LABELS[detail.statut]}
          </span>
          {estNouveau && (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
              Nouveau
            </span>
          )}
          {entrepriseNom && <span className="text-sm font-medium text-gray-500 bg-white px-3 py-1 rounded-full border border-gray-200">· {entrepriseNom}</span>}
        </div>

        <div className="grid grid-cols-12 gap-6 mb-6">
          
          {/* VISIONNEUSE DE DOCUMENT (GAUCHE) */}
          <div className="col-span-12 lg:col-span-5 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50/80 text-xs text-gray-500">
              <span className="font-medium text-gray-600">{detail.mime_type ?? "Type inconnu"}</span>
              <div className="flex items-center gap-1 bg-white border border-gray-200 rounded-md p-1 shadow-sm">
                <button onClick={() => setZoom((z) => Math.max(40, z - 20))} className="w-6 h-6 flex items-center justify-center hover:bg-gray-100 rounded text-gray-600 font-bold transition-colors" title="Zoom arrière">−</button>
                <span className="w-12 text-center font-medium">{zoom}%</span>
                <button onClick={() => setZoom((z) => Math.min(300, z + 20))} className="w-6 h-6 flex items-center justify-center hover:bg-gray-100 rounded text-gray-600 font-bold transition-colors" title="Zoom avant">+</button>
                <div className="w-px h-4 bg-gray-200 mx-1"></div>
                <a href={fileUrl} target="_blank" rel="noreferrer" className="px-2 text-green-600 hover:text-green-700 font-medium transition-colors">
                  Ouvrir ↗
                </a>
              </div>
            </div>
            
            <div className="flex-1 min-h-[520px] bg-slate-100 overflow-auto flex items-start justify-center p-4">
              {isImage && (
                <img src={fileUrl} alt={detail.nom_fichier_original} style={{ width: `${zoom}%` }} className="max-w-none shadow-md rounded transition-all duration-200" />
              )}
              {isPdf && (
                <iframe src={`${fileUrl}#toolbar=0`} title={detail.nom_fichier_original} className="w-full h-[600px] border-0 rounded shadow-sm bg-white" />
              )}
              {!isImage && !isPdf && (
                <div className="text-sm text-gray-500 p-8 text-center flex flex-col items-center justify-center h-full gap-4">
                  <span className="text-4xl">📄</span>
                  <p>Aperçu non disponible pour ce type de fichier.</p>
                  <a href={fileUrl} target="_blank" rel="noreferrer" className="px-4 py-2 bg-white border border-gray-200 rounded-md text-green-700 font-medium hover:bg-gray-50 transition-colors shadow-sm">
                    Télécharger / Ouvrir le fichier original ↗
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* INFORMATIONS EXTRAITES (CENTRE) */}
          <div className="col-span-12 lg:col-span-3 space-y-4">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span>🤖</span> Informations extraites (IA)
              </h2>
              {scoreCompletude !== null && (
                <div className="mb-5 bg-gray-50 p-3 rounded-lg border border-gray-100">
                  <div className="flex justify-between text-xs font-medium text-gray-500 mb-2">
                    <span>Score de complétude</span>
                    <span className="text-gray-800">{scoreCompletude}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full transition-all duration-500" style={{ width: `${scoreCompletude}%` }} />
                  </div>
                </div>
              )}
              <div className="space-y-3 text-sm divide-y divide-gray-50">
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
                        <div key={cle} className="flex justify-between gap-4 pt-2 first:pt-0">
                          <span className="text-gray-500 text-xs">{CHAMP_LABELS[cle] ?? cle}</span>
                          <span className="font-semibold text-gray-800 text-right break-all">{affichage}</span>
                        </div>
                      );
                    })}
                    {/* Champs additionnels non prévus dans CHAMP_ORDRE */}
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
                          <div key={cle} className="flex justify-between gap-4 pt-2">
                            <span className="text-gray-500 text-xs capitalize">{cle.replace(/_/g, " ")}</span>
                            <span className="font-semibold text-gray-800 text-right break-all">{affichage}</span>
                          </div>
                        );
                      })}
                  </>
                ) : (
                  <p className="text-gray-400 text-center py-4 italic">Pas encore de données extraites.</p>
                )}
              </div>
            </div>

            {/* VÉRIFICATIONS DE L'IA */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span>🛡️</span> Vérifications
              </h2>
              <div className="space-y-3 text-sm">
                {verifications.map((v) => (
                  <div key={v.label} className="flex items-center justify-between p-2 rounded bg-gray-50 border border-gray-100">
                    <span className={`text-xs font-medium ${v.ok === false ? "text-red-600" : "text-gray-600"}`}>{v.label}</span>
                    <span>
                      {v.ok === null ? (
                        <span className="text-gray-400 font-bold" title="Non vérifiable">—</span>
                      ) : v.ok ? (
                        <span className="text-green-500 font-bold text-lg leading-none" title="Vérification OK">✓</span>
                      ) : (
                        <span className="text-red-500 font-bold text-lg leading-none" title="Anomalie détectée">✕</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              {detail.ecriture?.anomalie_details && (
                <div className="mt-4 bg-orange-50 border border-orange-200 rounded-md p-3 flex gap-2 items-start">
                  <span className="text-orange-500 text-lg leading-none">⚠️</span>
                  <p className="text-xs text-orange-800 font-medium">{detail.ecriture.anomalie_details}</p>
                </div>
              )}
            </div>
          </div>

          {/* DÉTAILS BANQUE / COMPTABILITÉ (DROITE) */}
          <div className="col-span-12 lg:col-span-4 space-y-4">
            
            {/* ---- AFFICHAGE CONDITIONNEL : BANQUE OU ECRITURE CLASSIQUE ---- */}
            {detail.categorie === "banque" ? (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                  <span>🏦</span> Mouvements du relevé bancaire
                </h2>
                {detail.mouvements_bancaires && detail.mouvements_bancaires.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-gray-100">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr className="text-left text-gray-500 border-b border-gray-200">
                          <th className="px-3 py-2 font-semibold">Date</th>
                          <th className="px-3 py-2 font-semibold">Libellé</th>
                          <th className="px-3 py-2 font-semibold text-right">Débit</th>
                          <th className="px-3 py-2 font-semibold text-right">Crédit</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {detail.mouvements_bancaires.map((mvt) => (
                          <tr key={mvt.id} className="hover:bg-gray-50 transition-colors">
                            <td className="px-3 py-2.5 whitespace-nowrap text-gray-600">{mvt.date_operation}</td>
                            <td className="px-3 py-2.5 max-w-[120px] truncate font-medium text-gray-800" title={mvt.libelle}>{mvt.libelle}</td>
                            <td className="px-3 py-2.5 text-right text-red-600 font-semibold">
                              {mvt.type_mouvement === "DEBIT" ? Number(mvt.montant).toFixed(2) : ""}
                            </td>
                            <td className="px-3 py-2.5 text-right text-green-600 font-semibold">
                              {mvt.type_mouvement === "CREDIT" ? Number(mvt.montant).toFixed(2) : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 bg-gray-50 p-4 rounded-lg text-center border border-dashed border-gray-200">Aucun mouvement n'a encore été extrait pour ce relevé.</p>
                )}
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                  <span>🧮</span> Écriture comptable proposée
                </h2>
                {lignesEcriture.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-gray-100">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr className="text-left text-gray-500 border-b border-gray-200">
                          <th className="px-3 py-2 font-semibold">Compte</th>
                          <th className="px-3 py-2 font-semibold">Libellé</th>
                          <th className="px-3 py-2 font-semibold text-right">Débit</th>
                          <th className="px-3 py-2 font-semibold text-right">Crédit</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {lignesEcriture.map((ligne, idx) => (
                          <tr key={`${ligne.compte}-${idx}`} className="hover:bg-gray-50 transition-colors">
                            <td className="px-3 py-2.5 font-medium text-blue-600">{ligne.compte}</td>
                            <td className="px-3 py-2.5 text-gray-700">{ligne.libelle}</td>
                            <td className="px-3 py-2.5 text-right font-semibold text-gray-800">{ligne.debit ? parseFloat(ligne.debit).toFixed(2) : "-"}</td>
                            <td className="px-3 py-2.5 text-right font-semibold text-gray-800">{ligne.credit ? parseFloat(ligne.credit).toFixed(2) : "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 bg-gray-50 p-4 rounded-lg text-center border border-dashed border-gray-200">Pas encore d'écriture générée pour ce document.</p>
                )}
              </div>
            )}
            {/* ----------------------------------------------------------- */}

            {/* ZONE DE COMMENTAIRES */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-800 mb-3 flex items-center gap-2">
                <span>💬</span> Commentaires
              </h2>
              <textarea
                value={commentaireDraft}
                onChange={(e) => setCommentaireDraft(e.target.value)}
                placeholder="Ajouter un commentaire (Bientôt disponible)..."
                disabled
                rows={2}
                title="Bientôt disponible — nécessite une table de commentaires côté backend"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-400 cursor-not-allowed resize-none focus:outline-none"
              />
            </div>

            {/* HISTORIQUE */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                <span>⏱️</span> Historique
              </h2>
              <ul className="text-sm space-y-3 relative before:absolute before:inset-y-0 before:left-1.5 before:w-0.5 before:bg-gray-100 pl-4">
                <li className="flex justify-between items-start relative">
                  <span className="absolute -left-5 top-1.5 w-2.5 h-2.5 rounded-full bg-green-500 shadow-[0_0_0_2px_#fff]"></span>
                  <span className="text-gray-700 font-medium text-xs">Document importé</span>
                  <span className="text-gray-400 text-[10px]">{new Date(detail.created_at).toLocaleDateString("fr-FR")}</span>
                </li>
                {detail.statut !== "en_attente" && (
                  <li className="flex justify-between items-start relative">
                    <span className="absolute -left-5 top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_0_2px_#fff]"></span>
                    <span className="text-gray-700 font-medium text-xs">Extraction IA terminée</span>
                    <span className="text-gray-400 text-[10px]">—</span>
                  </li>
                )}
                {detail.ecriture && (
                  <li className="flex justify-between items-start relative">
                    <span className={`absolute -left-5 top-1.5 w-2.5 h-2.5 rounded-full shadow-[0_0_0_2px_#fff] ${detail.ecriture.statut_validation === 'valide' ? 'bg-green-500' : 'bg-yellow-400'}`}></span>
                    <span className="text-gray-700 font-medium text-xs">Écriture {VALIDATION_LABELS[detail.ecriture.statut_validation]}</span>
                    <span className="text-gray-400 text-[10px]">—</span>
                  </li>
                )}
              </ul>
            </div>

            {/* ACTIONS SUR LE DOCUMENT */}
            {detail.ecriture && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex gap-3 flex-wrap">
                <button
                  onClick={handleReject}
                  disabled={isProcessing || detail.ecriture.statut_validation === "rejete"}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-red-50 text-red-700 border border-red-100 hover:bg-red-100 hover:border-red-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  Rejeter
                </button>
                <button
                  onClick={ouvrirCorrection}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-yellow-50 text-yellow-700 border border-yellow-100 hover:bg-yellow-100 hover:border-yellow-200 transition-all"
                >
                  Corriger
                </button>
                <button
                  onClick={handleValidate}
                  disabled={isProcessing || detail.ecriture.statut_validation === "valide"}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all"
                >
                  Valider
                </button>
                <a
                  href={`http://localhost:8000/export/topaze/${detail.ecriture.id}?token=${localStorage.getItem("comptaflow_token")}`}
                  className="w-full mt-2 px-4 py-2 rounded-lg text-sm font-bold bg-slate-800 text-white hover:bg-slate-700 text-center shadow-sm transition-all flex items-center justify-center gap-2"
                >
                  <span>⬇️</span> Exporter vers Topaze
                </a>
              </div>
            )}
          </div>
        </div>

        {/* DOCUMENTS SIMILAIRES / CHRONOS */}
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 mb-4">
              <span className="font-bold text-gray-800 text-sm flex items-center gap-2"><span>📂</span> Chronos voisins</span>
              {entrepriseNom && <span className="bg-gray-100 px-2 py-0.5 rounded-full">{entrepriseNom}</span>}
              {detail.annee && <span className="bg-gray-100 px-2 py-0.5 rounded-full">{detail.annee}</span>}
              {detail.categorie && <span className="capitalize bg-gray-100 px-2 py-0.5 rounded-full">{detail.categorie}</span>}
            </div>
            
            <div className="flex gap-4 overflow-x-auto pb-3 snap-x">
              {siblingsFiltres.length === 0 && (
                <p className="text-sm text-gray-400 py-6 text-center w-full bg-gray-50 rounded-lg border border-dashed border-gray-200">
                  Aucun document trouvé pour ce classement.
                </p>
              )}
              {siblingsFiltres.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  className={`shrink-0 w-40 text-left border rounded-xl p-3 hover:border-green-400 hover:shadow-md transition-all snap-start ${
                    doc.id === detail.id ? "border-green-500 bg-green-50/50 shadow-sm ring-1 ring-green-500" : "border-gray-200 bg-white"
                  }`}
                >
                  <p className="text-xs font-bold text-gray-800 truncate mb-1" title={doc.nom_fichier_original}>{doc.nom_fichier_original}</p>
                  <div className="flex justify-between items-center mb-1">
                    <p className="text-[10px] text-gray-500 font-medium">
                      {doc.date_piece ? new Date(doc.date_piece).toLocaleDateString("fr-FR") : "Date inc."}
                    </p>
                  </div>
                  <p className="text-[11px] font-bold text-gray-900 mb-2">
                    {doc.montant_ttc ? `${parseFloat(doc.montant_ttc).toFixed(2)} DH` : "—"}
                  </p>
                  {doc.statut_validation && (
                    <span
                      className={`inline-block text-[10px] px-2 py-0.5 rounded-full font-medium ${
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

          <div className="col-span-12 lg:col-span-4 bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
              <span>🔍</span> Recherche rapide
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Nom de fichier</label>
                <input
                  type="text"
                  value={rechercheFooter}
                  onChange={(e) => setRechercheFooter(e.target.value)}
                  placeholder="Ex: Facture_01..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Statut</label>
                <select
                  value={filtreStatutFooter}
                  onChange={(e) => setFiltreStatutFooter(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 transition-all cursor-pointer"
                >
                  <option value="">Tous les statuts</option>
                  <option value="brouillon">Brouillon</option>
                  <option value="a_verifier">À vérifier</option>
                  <option value="valide">Validé</option>
                  <option value="rejete">Rejeté</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* MODALE DE CORRECTION D'ÉCRITURE */}
        {isEditing && detail.ecriture && (
          <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md animate-fade-in-up">
              <h2 className="text-lg font-bold text-gray-800 mb-5 border-b border-gray-100 pb-3">Corriger l'écriture comptable</h2>
              
              <div className="space-y-4">
                <div>
                  <label htmlFor="edit-tiers" className="block text-xs font-bold text-gray-600 mb-1">Tiers (Client / Fournisseur)</label>
                  <input
                    id="edit-tiers"
                    type="text"
                    value={editForm.tiers}
                    onChange={(e) => setEditForm({ ...editForm, tiers: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="edit-num" className="block text-xs font-bold text-gray-600 mb-1">N° pièce</label>
                    <input
                      id="edit-num"
                      type="text"
                      value={editForm.numero_piece}
                      onChange={(e) => setEditForm({ ...editForm, numero_piece: e.target.value })}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="edit-date" className="block text-xs font-bold text-gray-600 mb-1">Date pièce</label>
                    <input
                      id="edit-date"
                      type="date"
                      value={editForm.date_piece}
                      onChange={(e) => setEditForm({ ...editForm, date_piece: e.target.value })}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-3 pt-2">
                  <div>
                    <label htmlFor="edit-ht" className="block text-xs font-bold text-gray-600 mb-1">HT</label>
                    <input
                      id="edit-ht"
                      type="number" step="0.01"
                      value={editForm.montant_ht}
                      onChange={(e) => setEditForm({ ...editForm, montant_ht: e.target.value })}
                      className="w-full border border-gray-300 rounded-lg px-2 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="edit-tva" className="block text-xs font-bold text-gray-600 mb-1">TVA</label>
                    <input
                      id="edit-tva"
                      type="number" step="0.01"
                      value={editForm.montant_tva}
                      onChange={(e) => setEditForm({ ...editForm, montant_tva: e.target.value })}
                      className="w-full border border-gray-300 rounded-lg px-2 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="edit-ttc" className="block text-xs font-bold text-gray-600 mb-1">TTC</label>
                    <input
                      id="edit-ttc"
                      type="number" step="0.01"
                      value={editForm.montant_ttc}
                      onChange={(e) => setEditForm({ ...editForm, montant_ttc: e.target.value })}
                      className="w-full border border-gray-300 rounded-lg px-2 py-2 text-sm font-medium bg-gray-50 focus:outline-none focus:ring-2 focus:ring-green-500/30 focus:border-green-500"
                    />
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-100">
                <button onClick={() => setIsEditing(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                  Annuler
                </button>
                <button
                  onClick={enregistrerCorrection}
                  disabled={isProcessing}
                  className="px-5 py-2 rounded-lg text-sm font-bold bg-green-600 text-white hover:bg-green-700 shadow-sm disabled:opacity-50 transition-colors"
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