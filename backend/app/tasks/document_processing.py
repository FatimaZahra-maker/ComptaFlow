"""
app/tasks/document_processing.py

Orchestrateur Celery du traitement documentaire.

Pipeline principal :

1. Groq Vision en priorité
2. Classification + extraction dans le même appel Vision
3. Si Vision échoue :
      texte natif PDF
      ou PaddleOCR
4. Extraction depuis texte
5. Identification de l'entreprise
6. Détermination achats / ventes
7. Classement dans le chrono
8. Création écriture comptable ou mouvements bancaires

Pour un relevé bancaire :

- la première page est classifiée ET extraite par le même appel Vision ;
- la même page n'est plus envoyée une deuxième fois à Groq ;
- les pages suivantes utilisent le service bancaire spécialisé ;
- aucune ligne bancaire n'est dédupliquée ;
- les totaux et soldes sont ensuite validés par bank_statement_service.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import date, datetime

import psutil

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import (
    ErreurPipelineDefinitive,
    ErreurPipelineTransitoire,
    OCRVideError,
    PeriodeComptableVerrouilleeError,
)
from app.models.document import Document
from app.models.entreprise import Entreprise
from app.models.enums import (
    StatutDocumentEnum,
    TypeErreurEnum,
)
from app.services import (
    accounting_service,
    ai_service,
    audit_service,
    anomaly_service,
    bank_statement_service,
    chrono_service,
    company_service,
    ocr_service,
    preprocessing_service,
    vision_service,
    workflow_comptable_service,
)
from app.services.document_classifier import (
    detecter_type_document,
)



def _extraire_annee_mois(date_piece, document: Document) -> tuple[int, int]:
    """
    Lit les formats de date réellement rencontrés dans les factures.

    Formats acceptés :
    - YYYY-MM-DD
    - DD/MM/YYYY
    - DD-MM-YYYY
    - DD.MM.YYYY

    Si la date est absente/illisible, on conserve created_at uniquement comme
    secours technique pour le rangement interne année/mois.
    """
    if isinstance(date_piece, datetime):
        return date_piece.year, date_piece.month

    if date_piece not in (None, ""):
        texte = str(date_piece).strip()
        for format_date in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(texte[:10], format_date)
                return parsed.year, parsed.month
            except ValueError:
                continue

    return document.created_at.year, document.created_at.month

# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(
    "comptaflow.pipeline"
)


# ============================================================
# LIMITES DE SÉCURITÉ
# ============================================================

# Pour facture / CNSS / TVA / chèque / autre :
# quelques pages suffisent pour trouver une page exploitable.
MAX_PAGES_VISION_TENTEES = 3


# Pour un relevé bancaire multi-pages, on doit pouvoir
# traiter beaucoup plus de pages.
MAX_PAGES_RELEVE_BANCAIRE = 50


def _erreur_est_transitoire(exc: Exception) -> bool:
    """Autorise un retry uniquement pour une panne réseau/service temporaire."""
    if isinstance(exc, (ErreurPipelineTransitoire, TimeoutError, ConnectionError)):
        return True
    statut = getattr(exc, "status_code", None)
    if statut is None:
        statut = getattr(getattr(exc, "response", None), "status_code", None)
    return statut == 429 or (isinstance(statut, int) and 500 <= statut <= 599)


# ============================================================
# RAM
# ============================================================

def _log_ram(
    etape: str,
    document_id: str,
) -> None:
    """
    Log la RAM utilisée par le worker Python.

    Utile pour surveiller PaddleOCR, Ollama et
    les traitements de gros documents.
    """

    mem_mb = (
        psutil.Process(
            os.getpid()
        )
        .memory_info()
        .rss
        / (
            1024
            * 1024
        )
    )

    logger.info(
        "Document %s | RAM après '%s' : %.1f MB",
        document_id,
        etape,
        mem_mb,
    )


# ============================================================
# WRAPPER D'ÉTAPE
# ============================================================

def _executer_etape(
    nom_etape: str,
    document_id: str,
    fonction,
    *args,
    **kwargs,
):
    """
    Exécute une étape du pipeline.

    Mesure automatiquement :

    - début ;
    - durée ;
    - succès ;
    - erreur.

    Les exceptions ne sont PAS supprimées.
    Elles remontent jusqu'à process_document().
    """

    debut = time.perf_counter()

    logger.info(
        "Document %s | Étape '%s' -- démarrage",
        document_id,
        nom_etape,
    )

    try:

        resultat = fonction(
            *args,
            **kwargs,
        )

    except Exception:

        duree = (
            time.perf_counter()
            - debut
        )

        logger.exception(
            "Document %s | Étape '%s' -- "
            "ÉCHEC après %.2fs",
            document_id,
            nom_etape,
            duree,
        )

        raise


    duree = (
        time.perf_counter()
        - debut
    )

    logger.info(
        "Document %s | Étape '%s' -- "
        "OK en %.2fs",
        document_id,
        nom_etape,
        duree,
    )

    return resultat


# ============================================================
# OCR / TEXTE NATIF
# ============================================================

def _extraire_texte_ocr(
    document: Document,
) -> str:
    """
    Extrait le texte complet d'un document.

    Priorité :

    PDF avec couche texte
        ↓
    extraction native PyMuPDF

    sinon

    page prétraitée
        ↓
    PaddleOCR

    Les pages sont traitées une par une afin
    d'éviter de charger tout le document en RAM.
    """

    # --------------------------------------------------------
    # 1. PDF NATIF
    # --------------------------------------------------------

    texte_natif = (
        preprocessing_service
        .extraire_texte_natif_pdf(
            document.chemin_stockage
        )
    )

    if texte_natif is not None:

        return texte_natif


    # --------------------------------------------------------
    # 2. OCR PAGE PAR PAGE
    # --------------------------------------------------------

    textes_pages: list[str] = []

    dernier_chemin_page: str | None = None


    try:

        for chemin_page in (
            preprocessing_service
            .generer_pages_pretraitees(
                document.chemin_stockage
            )
        ):

            dernier_chemin_page = (
                chemin_page
            )

            try:

                texte_page = (
                    ocr_service
                    .extraire_texte_page(
                        chemin_page
                    )
                )


                if texte_page.strip():

                    textes_pages.append(
                        texte_page
                    )


            finally:

                (
                    preprocessing_service
                    .nettoyer_fichier_temporaire(
                        chemin_page
                    )
                )


    finally:

        if (
            dernier_chemin_page
            is not None
        ):

            (
                preprocessing_service
                .nettoyer_dossier_document(
                    dernier_chemin_page
                )
            )


    # --------------------------------------------------------
    # ASSEMBLAGE
    # --------------------------------------------------------

    texte_final = "\n".join(
        textes_pages
    )


    if not texte_final.strip():

        raise OCRVideError(
            "L'OCR n'a extrait aucun texte du document "
            "(fichier vide, illisible, ou image trop dégradée)."
        )


    return texte_final


# ============================================================
# DÉTECTION BANQUE
# ============================================================

def _est_releve_bancaire(
    donnees: dict | None,
) -> bool:
    """
    Vérifie si le résultat d'extraction correspond
    à un relevé bancaire.
    """

    if not donnees:
        return False


    return (

        donnees.get(
            "type_document"
        )
        == "releve_bancaire"

        or

        donnees.get(
            "categorie_document"
        )
        == "releve_bancaire"

        or

        donnees.get(
            "categorie"
        )
        == "banque"
    )


# ============================================================
# GROQ VISION
# ============================================================

def _tenter_vision_multi_pages(
    document: Document,
    document_id: str,
) -> dict | None:
    """
    Tente l'extraction Vision page par page.

    IMPORTANT :

    Pour la première page :

        Groq Vision
            ↓
        classification
            +
        extraction

    dans UN SEUL appel.


    Si cette page est un relevé bancaire :

        le résultat contient déjà
        les lignes bancaires.

    On ne renvoie donc PAS la même page une
    deuxième fois à Groq.


    Pour un relevé bancaire multi-pages :

        page 1
          ↓
        Vision unifiée

        page 2+
          ↓
        extraction bancaire spécialisée


    Pour facture / CNSS / TVA / chèque / autre :

        le premier résultat Vision exploitable
        est directement retourné.


    Aucune déduplication des opérations bancaires
    n'est effectuée.
    """

    # --------------------------------------------------------
    # GROQ NON CONFIGURÉ
    # --------------------------------------------------------

    if not settings.GROQ_API_KEY:

        return None


    pages_tentees = 0

    mode_banque = False

    pages_bancaires: list[dict] = []

    dernier_chemin_page: str | None = None


    try:

        # ====================================================
        # PAGE PAR PAGE
        # ====================================================

        for chemin_page in (
            preprocessing_service
            .generer_pages_pretraitees(
                document.chemin_stockage
            )
        ):

            dernier_chemin_page = (
                chemin_page
            )

            pages_tentees += 1


            try:

                # =================================================
                # RELEVÉ BANCAIRE DÉJÀ IDENTIFIÉ
                # =================================================
                #
                # Si page 1 a déjà montré qu'il s'agit
                # d'un relevé bancaire, les pages suivantes
                # utilisent directement le service banque.

                if mode_banque:

                    if (
                        pages_tentees
                        > MAX_PAGES_RELEVE_BANCAIRE
                    ):

                        logger.warning(
                            "Document %s | "
                            "Relevé limité à %s pages "
                            "pour sécurité.",
                            document_id,
                            MAX_PAGES_RELEVE_BANCAIRE,
                        )

                        break


                    page_banque = (
                        _executer_etape(
                            (
                                "extraction_banque_page_"
                                f"{pages_tentees}"
                            ),
                            document_id,
                            (
                                bank_statement_service
                                .extraire_page_depuis_image
                            ),
                            chemin_page,
                            pages_tentees,
                        )
                    )


                    if (
                        page_banque
                        is not None
                    ):

                        pages_bancaires.append(
                            page_banque
                        )


                    continue


                # =================================================
                # VISION GÉNÉRIQUE
                # =================================================
                #
                # Tant qu'on ne connaît pas encore le type,
                # on utilise Vision générale.

                if (
                    pages_tentees
                    > MAX_PAGES_VISION_TENTEES
                ):

                    break


                donnees_vision = (
                    _executer_etape(
                        (
                            "extraction_vision_page_"
                            f"{pages_tentees}"
                        ),
                        document_id,
                        (
                            vision_service
                            .extraire_et_classifier_depuis_image
                        ),
                        chemin_page,
                    )
                )


                # Vision échouée :
                # essayer éventuellement une page suivante.
                if (
                    donnees_vision
                    is None
                ):

                    continue


                # =================================================
                # PREMIÈRE PAGE BANCAIRE
                # =================================================

                if (
                    _est_releve_bancaire(
                        donnees_vision
                    )
                ):

                    mode_banque = True


                    # IMPORTANT :
                    #
                    # vision_service a DÉJÀ extrait
                    # les transactions de cette page.
                    #
                    # Ancien comportement :
                    #
                    # Vision #1
                    #   ↓
                    # classification banque
                    #   ↓
                    # Vision #2
                    #   ↓
                    # extraction banque
                    #
                    # Nouveau comportement :
                    #
                    # Vision #1
                    #   ↓
                    # classification + extraction
                    #
                    # Donc aucun deuxième appel ici.

                    donnees_vision[
                        "page"
                    ] = pages_tentees


                    pages_bancaires.append(
                        donnees_vision
                    )


                    continue


                # =================================================
                # AUTRES DOCUMENTS
                # =================================================
                #
                # Cela peut représenter :
                #
                # facture
                # CNSS
                # TVA
                # chèque
                # reçu
                # avis bancaire
                # document fiscal
                # autre
                #
                # Achat / vente sera déterminé plus tard
                # par company_service.

                return donnees_vision


            finally:

                # Toujours supprimer la page temporaire.

                (
                    preprocessing_service
                    .nettoyer_fichier_temporaire(
                        chemin_page
                    )
                )


    finally:

        # Nettoyage du dossier temporaire complet.

        if (
            dernier_chemin_page
            is not None
        ):

            (
                preprocessing_service
                .nettoyer_dossier_document(
                    dernier_chemin_page
                )
            )


    # ========================================================
    # NORMALISATION + VALIDATION BANCAIRE
    # ========================================================

    if (
        mode_banque
        and pages_bancaires
    ):

        return (
            bank_statement_service
            .normaliser_et_valider_releve(
                pages_bancaires,
                source="groq_vision_banque",
            )
        )


    # ========================================================
    # VISION ÉCHOUÉE
    # ========================================================

    logger.warning(
        "Document %s | "
        "Vision indisponible/échouée sur %s page(s) -- "
        "repli extraction natif/PaddleOCR.",
        document_id,
        pages_tentees,
    )


    return None


# ============================================================
# CASCADE EXTRACTION
# ============================================================

def _extraire_donnees_par_vision_ou_ocr(
    document: Document,
    document_id: str,
) -> tuple[dict, str]:
    """
    Cascade principale d'extraction.

    Ordre :

    1. Groq Vision
    2. Si Vision réussit :
          retour immédiat
    3. Sinon :
          texte natif / PaddleOCR
    4. Si relevé bancaire :
          Groq texte bancaire
    5. Sinon :
          ai_service
          avec Groq texte / Regex / Ollama selon
          le fonctionnement interne du service.
    """

    # --------------------------------------------------------
    # 1. GROQ VISION
    # --------------------------------------------------------

    donnees_vision = (
        _tenter_vision_multi_pages(
            document,
            document_id,
        )
    )


    if (
        donnees_vision
        is not None
    ):

        # Pas de texte OCR nécessaire lorsque
        # Vision a réussi.

        return (
            donnees_vision,
            "",
        )


    # --------------------------------------------------------
    # 2. TEXTE NATIF OU PADDLEOCR
    # --------------------------------------------------------

    texte = (
        _executer_etape(
            "ocr_ou_natif",
            document_id,
            _extraire_texte_ocr,
            document,
        )
    )


    # --------------------------------------------------------
    # 3. FALLBACK BANQUE
    # --------------------------------------------------------
    #
    # La branche dédiée Banque depuis texte n'est
    # utilisée que lorsque le classifieur local reconnaît
    # un relevé bancaire.

    if (
        detecter_type_document(
            texte
        )
        == "releve_bancaire"
    ):

        donnees_banque = (
            _executer_etape(
                "extraction_banque_texte",
                document_id,
                (
                    bank_statement_service
                    .extraire_releve_depuis_texte
                ),
                texte,
            )
        )


        if (
            donnees_banque
            is not None
        ):

            return (
                donnees_banque,
                texte,
            )


    # --------------------------------------------------------
    # 4. AUTRES DOCUMENTS
    # --------------------------------------------------------

    donnees = (
        _executer_etape(
            "extraction_donnees",
            document_id,
            ai_service.extraire_donnees,
            texte,
        )
    )


    donnees.setdefault(
        "source_extraction",
        "ocr_texte",
    )


    return (
        donnees,
        texte,
    )


# ============================================================
# GESTION ERREUR
# ============================================================

def _marquer_erreur(
    db,
    document_id: str,
    message: str,
    type_erreur: TypeErreurEnum,
    error_code: str,
) -> None:
    """
    Enregistre l'état erreur du document en base.
    """

    document = (
        db.query(
            Document
        )
        .filter(
            Document.id
            == document_id
        )
        .first()
    )


    if document:

        document.statut = (
            StatutDocumentEnum
            .ERREUR
        )

        document.message_erreur = (
            message
        )

        document.type_erreur = (
            type_erreur
        )

        document.error_code = (
            error_code
        )

        audit_service.enregistrer(
            db, user=document.uploaded_by_user,
            action="DOCUMENT_PROCESSING_FAILED", entreprise_id=document.entreprise_id,
            resource_type="document", resource_id=document.id, actor_type="celery",
            status="failed", description="Échec du traitement automatique du document.",
            metadata={"error_code": error_code, "error_type": type_erreur},
        )

        db.commit()


# ============================================================
# CELERY TASK
# ============================================================

@celery_app.task(
    name="process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_document(
    self,
    document_id: str,
):
    """
    Tâche Celery principale ComptaFlow.

    Elle orchestre :

    extraction
        ↓
    identification entreprise
        ↓
    achats / ventes / catégories métier
        ↓
    chrono
        ↓
    stockage
        ↓
    écriture comptable
        OU
    mouvements bancaires
    """

    db = SessionLocal()


    try:

        # ====================================================
        # CHARGEMENT DOCUMENT
        # ====================================================

        document = (
            db.query(
                Document
            )
            .filter(
                Document.id
                == document_id
            )
            .first()
        )


        if document is None:

            logger.warning(
                "Document %s introuvable en base, "
                "tâche ignorée.",
                document_id,
            )

            return

        entreprise_forcee_id = (document.donnees_extraites or {}).get(
            "_entreprise_forcee_id"
        )

        # Une tâche mise en file avant le verrouillage ne doit pas contourner
        # le passage ultérieur de la période en lecture seule.
        workflow_comptable_service.verifier_document_modifiable(db, document)


        # ====================================================
        # PASSAGE EN TRAITEMENT
        # ====================================================

        document.statut = (
            StatutDocumentEnum
            .EN_TRAITEMENT
        )

        document.message_erreur = None

        document.type_erreur = None

        document.error_code = None

        db.commit()


        # ====================================================
        # EXTRACTION
        # ====================================================

        donnees, texte = (
            _extraire_donnees_par_vision_ou_ocr(
                document,
                document_id,
            )
        )


        document.texte_ocr = (
            texte
        )

        document.donnees_extraites = (
            donnees
        )

        db.commit()


        _log_ram(
            "extraction",
            document_id,
        )


        # ====================================================
        # IDENTIFICATION ENTREPRISE + DIRECTION
        # ====================================================
        #
        # Pour une facture :
        #
        # entreprise cabinet = fournisseur
        #     → vente
        #
        # entreprise cabinet = client
        #     → achat
        #
        # Cette décision n'est donc PAS faite
        # aveuglément par Groq.

        (
            entreprise,
            direction,
            tiers_detecte,
        ) = _executer_etape(
            "identification_entreprise",
            document_id,
            (
                company_service
                .identifier_entreprise_et_direction
            ),
            db,
            document.cabinet_id,
            donnees,
        )

        if entreprise_forcee_id:
            entreprise_detectee_id = getattr(entreprise, "id", None)
            entreprise_forcee = (
                db.query(Entreprise)
                .filter(
                    Entreprise.id == uuid.UUID(str(entreprise_forcee_id)),
                    Entreprise.cabinet_id == document.cabinet_id,
                    Entreprise.is_active.is_(True),
                    Entreprise.creee_automatiquement.is_(False),
                )
                .first()
            )
            if entreprise_forcee is None:
                raise ValueError(
                    "L'entreprise attribuée manuellement n'est plus disponible dans ce cabinet."
                )
            entreprise = entreprise_forcee
            if entreprise_detectee_id not in (None, entreprise_forcee.id):
                direction = None
                donnees["direction_a_verifier"] = True
                donnees["raison_direction"] = (
                    "L'attribution manuelle diffère de l'identification automatique ; "
                    "le sens achat/vente doit être vérifié."
                )
            donnees["_entreprise_forcee_id"] = str(entreprise_forcee.id)
            donnees["source_identification_entreprise"] = "attribution_manuelle"
            donnees["identification_entreprise_a_verifier"] = False


        # ====================================================
        # CATÉGORIE
        # ====================================================

        if direction is not None:

            donnees[
                "categorie"
            ] = direction


        elif donnees.get(
            "type_document"
        ) in (
            "releve_bancaire",
            "avis_cnss",
            "avis_tva",
        ):

            donnees[
                "categorie"
            ] = {

                "releve_bancaire":
                    "banque",

                "avis_cnss":
                    "cnss",

                "avis_tva":
                    "tva",

            }[
                donnees[
                    "type_document"
                ]
            ]


        # ====================================================
        # TIERS
        # ====================================================

        if tiers_detecte:

            donnees[
                "tiers"
            ] = tiers_detecte


        annee, mois = _extraire_annee_mois(
            donnees.get("date_piece"),
            document,
        )

        # Sauvegarder la version enrichie et rattacher immédiatement
        # le dossier comptable quand il existe. Une facture propre au cabinet
        # SEGURIBAT peut volontairement rester sans entreprise_id.

        entreprise_id = (
            entreprise.id
            if entreprise is not None
            else None
        )

        if entreprise_id is not None:
            workflow_comptable_service.verifier_date_modifiable(
                db,
                cabinet_id=document.cabinet_id,
                entreprise_id=entreprise_id,
                target_date=date(annee, mois, 1),
            )

        document.entreprise_id = entreprise_id
        document.donnees_extraites = dict(donnees)
        db.commit()


        # ====================================================
        # DOUBLON MÉTIER FORT -- AVANT CHRONO / ÉCRITURE
        # ====================================================

        document_doublon = (
            _executer_etape(
                "detection_doublon_metier",
                document_id,
                anomaly_service.trouver_document_doublon_metier,
                db,
                document,
                entreprise_id,
                donnees,
            )
        )

        if document_doublon is not None:

            _executer_etape(
                "marquage_doublon",
                document_id,
                anomaly_service.marquer_document_comme_doublon,
                db,
                document,
                document_doublon,
                donnees,
            )

            logger.warning(
                "Document %s | Doublon métier du document %s -- "
                "aucun chrono et aucune écriture créés.",
                document_id,
                document_doublon.id,
            )

            audit_service.enregistrer(
                db, user=document.uploaded_by_user,
                action="DOCUMENT_DUPLICATE_DETECTED",
                entreprise_id=document.entreprise_id, resource_type="document",
                resource_id=document.id, actor_type="celery",
                description="Doublon métier détecté par le traitement automatique.",
                metadata={"original_document_id": document_doublon.id},
                resource_ids=[document.id, document_doublon.id], item_count=2,
            )
            db.commit()

            return


        # ====================================================
        # ANNÉE / MOIS INTERNES
        # ====================================================

        # ====================================================
        # FACTURE PROPRE AU CABINET
        # ====================================================
        #
        # SEGURIBAT est le cabinet, pas une Entreprise suivie.
        # Quand aucune autre entreprise suivie n'est concernée, on conserve
        # la pièce comme document du cabinet, sans créer artificiellement un
        # chrono entreprise ni une écriture dans un faux dossier.

        if entreprise is None:
            document.entreprise_id = None
            document.chrono_id = None
            document.annee = annee
            document.mois = mois
            document.categorie = (
                donnees.get("categorie")
                or "divers"
            )
            document.statut = StatutDocumentEnum.TRAITE
            document.donnees_extraites = dict(donnees)
            audit_service.enregistrer(
                db, user=document.uploaded_by_user,
                action="DOCUMENT_CLASSIFIED", resource_type="document",
                resource_id=document.id, actor_type="celery",
                description="Document du cabinet classifié automatiquement.",
                apres={"categorie": document.categorie, "statut": document.statut},
                metadata={"source_extraction": donnees.get("source_extraction")},
            )
            db.commit()

            logger.info(
                "Document %s | Facture propre au cabinet %s : "
                "conservée sans chrono entreprise ni écriture automatique.",
                document_id,
                donnees.get("cabinet_nom") or "cabinet",
            )

            return


        # ====================================================
        # CHRONO ENTREPRISE
        # ====================================================

        chrono = (
            _executer_etape(
                "chrono",
                document_id,
                (
                    chrono_service
                    .obtenir_ou_creer_chrono
                ),
                db,
                document.cabinet_id,
                entreprise.id,
            )
        )


        # ====================================================
        # MISE À JOUR DOCUMENT
        # ====================================================

        document.entreprise_id = entreprise.id
        document.chrono_id = chrono.id
        document.annee = annee
        document.mois = mois
        document.categorie = (
            donnees.get("categorie")
            or "divers"
        )
        document.statut = StatutDocumentEnum.TRAITE
        document.donnees_extraites = dict(donnees)
        db.commit()


        # ====================================================
        # BANQUE
        # ====================================================

        if (
            str(
                getattr(
                    document.categorie,
                    "value",
                    document.categorie,
                )
            )
            == "banque"
        ):

            mouvements = (
                _executer_etape(
                    "creation_mouvements_bancaires",
                    document_id,
                    (
                        accounting_service
                        .creer_mouvements_bancaires
                    ),
                    db,
                    document,
                )
            )


            logger.info(
                "Document %s | "
                "Relevé bancaire traité : "
                "%s ligne(s) conservée(s), "
                "statut extraction=%s",
                document_id,
                len(
                    mouvements
                ),
                donnees.get(
                    "extraction_bancaire_statut",
                    "inconnu",
                ),
            )


        # ====================================================
        # FACTURE / CNSS / TVA / AUTRES
        # ====================================================

        else:

            ecriture = (
                _executer_etape(
                    "creation_ecriture",
                    document_id,
                    (
                        accounting_service
                        .creer_ecriture_depuis_document
                    ),
                    db,
                    document,
                )
            )


            _executer_etape(
                "detection_doublon",
                document_id,
                (
                    anomaly_service
                    .appliquer_detection_doublon
                ),
                db,
                ecriture,
            )


            logger.info(
                "Document %s | "
                "Pipeline document comptable terminé.",
                document_id,
            )

        audit_service.enregistrer(
            db, user=document.uploaded_by_user,
            action="DOCUMENT_CLASSIFIED", entreprise_id=document.entreprise_id,
            resource_type="document", resource_id=document.id, actor_type="celery",
            description="Extraction et classification automatiques terminées.",
            apres={
                "categorie": document.categorie, "statut": document.statut,
                "entreprise_id": document.entreprise_id,
            },
            metadata={
                "source_extraction": donnees.get("source_extraction"),
                "type_document": donnees.get("type_document"),
            },
        )
        db.commit()


    # ========================================================
    # ERREUR DÉFINITIVE
    # ========================================================

    except ErreurPipelineDefinitive as exc:

        db.rollback()


        logger.error(
            "Document %s | "
            "Erreur définitive [%s] : %s",
            document_id,
            exc.code,
            exc,
        )


        _marquer_erreur(
            db,
            document_id,
            str(
                exc
            ),
            TypeErreurEnum.DEFINITIVE,
            exc.code,
        )


    except PeriodeComptableVerrouilleeError as exc:

        db.rollback()
        logger.warning("Document %s refusé : période verrouillée.", document_id)
        _marquer_erreur(
            db,
            document_id,
            str(exc),
            TypeErreurEnum.DEFINITIVE,
            "PERIODE_VERROUILLEE",
        )
        return


    # ========================================================
    # ERREUR TRANSITOIRE
    # ========================================================

    except Exception as exc:

        db.rollback()

        if not _erreur_est_transitoire(exc):
            logger.exception(
                "Document %s | Erreur non transitoire non classée : %s",
                document_id,
                type(exc).__name__,
            )
            _marquer_erreur(
                db, document_id, str(exc), TypeErreurEnum.DEFINITIVE,
                "UNEXPECTED_DEFINITIVE_ERROR",
            )
            return


        _marquer_erreur(
            db,
            document_id,
            str(
                exc
            ),
            TypeErreurEnum.TRANSITOIRE,
            "TRANSIENT_ERROR",
        )


        # ----------------------------------------------------
        # MAX RETRIES ATTEINT
        # ----------------------------------------------------

        if (
            self.request.retries
            >= self.max_retries
        ):

            logger.error(
                "Document %s | "
                "Échec définitif après %s tentatives : %s",
                document_id,
                self.request.retries,
                exc,
            )

            return


        # ----------------------------------------------------
        # RETRY CELERY
        # ----------------------------------------------------

        logger.warning(
            "Document %s | "
            "Tentative %s/%s échouée, "
            "retry programmé : %s",
            document_id,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )


        raise self.retry(
            exc=exc
        )


    # ========================================================
    # FERMETURE DB
    # ========================================================

    finally:

        db.close()
