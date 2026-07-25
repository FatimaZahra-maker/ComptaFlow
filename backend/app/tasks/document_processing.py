"""
app/tasks/document_processing.py

Orchestrateur Celery : extraction (vision Groq en priorité, repli
PaddleOCR + cascade texte) + identification entreprise/direction +
chrono + classement + écriture comptable + détection de doublon.

CORRECTIF (nettoyage du dossier temporaire) : le nettoyage du dossier
entier (nettoyer_dossier_document) n'est désormais appelé qu'UNE SEULE
FOIS, après la fin complète de la consommation du générateur de pages
-- plus jamais à chaque itération (voir preprocessing_service.py pour
le détail du bug corrigé : le dossier partagé se supprimait lui-même
entre deux pages, cassant la génération de la page suivante).
"""
import logging
import os
import time
import psutil
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ErreurPipelineDefinitive, OCRVideError
from app.models.document import Document
from app.models.enums import StatutDocumentEnum, TypeErreurEnum
from app.services import (
    preprocessing_service,
    ocr_service,
    ai_service,
    vision_service,
    company_service,
    chrono_service,
    accounting_service,
    anomaly_service,
)

logger = logging.getLogger("comptaflow.pipeline")

MAX_PAGES_VISION_TENTEES = 3


def _log_ram(etape: str, document_id: str) -> None:
    mem_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    logger.info("Document %s | RAM après '%s' : %.1f MB", document_id, etape, mem_mb)


def _executer_etape(nom_etape: str, document_id: str, fonction, *args, **kwargs):
    debut = time.perf_counter()
    logger.info("Document %s | Étape '%s' -- démarrage", document_id, nom_etape)
    try:
        resultat = fonction(*args, **kwargs)
    except Exception:
        duree = time.perf_counter() - debut
        logger.exception(
            "Document %s | Étape '%s' -- ÉCHEC après %.2fs", document_id, nom_etape, duree
        )
        raise
    duree = time.perf_counter() - debut
    logger.info("Document %s | Étape '%s' -- OK en %.2fs", document_id, nom_etape, duree)
    return resultat


def _extraire_texte_ocr(document: Document) -> str:
    texte_natif = preprocessing_service.extraire_texte_natif_pdf(document.chemin_stockage)
    if texte_natif is not None:
        return texte_natif

    textes_pages: list[str] = []
    dernier_chemin_page: str | None = None
    try:
        for chemin_page in preprocessing_service.generer_pages_pretraitees(document.chemin_stockage):
            dernier_chemin_page = chemin_page
            try:
                texte_page = ocr_service.extraire_texte_page(chemin_page)
                if texte_page.strip():
                    textes_pages.append(texte_page)
            finally:
                preprocessing_service.nettoyer_fichier_temporaire(chemin_page)
    finally:
        if dernier_chemin_page is not None:
            preprocessing_service.nettoyer_dossier_document(dernier_chemin_page)

    texte_final = "\n".join(textes_pages)
    if not texte_final.strip():
        raise OCRVideError(
            "L'OCR n'a extrait aucun texte du document (fichier vide, "
            "illisible, ou image trop dégradée)."
        )
    return texte_final


def _tenter_vision_multi_pages(document: Document, document_id: str) -> dict | None:
    if not settings.GROQ_API_KEY:
        return None

    pages_tentees = 0
    dernier_chemin_page: str | None = None
    try:
        for chemin_page in preprocessing_service.generer_pages_pretraitees(document.chemin_stockage):
            dernier_chemin_page = chemin_page
            try:
                if pages_tentees >= MAX_PAGES_VISION_TENTEES:
                    break
                pages_tentees += 1

                donnees_vision = _executer_etape(
                    f"extraction_vision_page_{pages_tentees}", document_id,
                    vision_service.extraire_et_classifier_depuis_image, chemin_page,
                )
                if donnees_vision is not None:
                    return donnees_vision
            finally:
                preprocessing_service.nettoyer_fichier_temporaire(chemin_page)
    finally:
        if dernier_chemin_page is not None:
            preprocessing_service.nettoyer_dossier_document(dernier_chemin_page)

    logger.warning(
        "Document %s | Vision Groq indisponible/échouée sur %s page(s) -- "
        "repli extraction natif/PaddleOCR.", document_id, pages_tentees,
    )
    return None


def _extraire_donnees_par_vision_ou_ocr(document: Document, document_id: str) -> tuple[dict, str]:
    donnees_vision = _tenter_vision_multi_pages(document, document_id)
    if donnees_vision is not None:
        return donnees_vision, ""

    texte = _executer_etape(
        "ocr_ou_natif", document_id, _extraire_texte_ocr, document,
    )
    donnees = _executer_etape(
        "extraction_donnees", document_id, ai_service.extraire_donnees, texte,
    )
    donnees.setdefault("source_extraction", "ocr_texte")
    return donnees, texte


def _marquer_erreur(db, document_id: str, message: str, type_erreur: TypeErreurEnum, error_code):
    document = db.query(Document).filter(Document.id == document_id).first()
    if document:
        document.statut = StatutDocumentEnum.ERREUR
        document.message_erreur = message
        document.type_erreur = type_erreur
        document.error_code = error_code
        db.commit()


@celery_app.task(
    name="process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_document(self, document_id: str):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            logger.warning("Document %s introuvable en base, tâche ignorée.", document_id)
            return

        document.statut = StatutDocumentEnum.EN_TRAITEMENT
        db.commit()

        donnees, texte = _extraire_donnees_par_vision_ou_ocr(document, document_id)
        document.texte_ocr = texte
        document.donnees_extraites = donnees
        db.commit()
        _log_ram("extraction", document_id)

        entreprise, direction, tiers_detecte = _executer_etape(
            "identification_entreprise", document_id,
            company_service.identifier_entreprise_et_direction,
            db, document.cabinet_id, donnees,
        )
        if direction is not None:
            donnees["categorie"] = direction
        elif donnees.get("type_document") in ("releve_bancaire", "avis_cnss", "avis_tva"):
            donnees["categorie"] = {
                "releve_bancaire": "banque",
                "avis_cnss": "cnss",
                "avis_tva": "tva",
            }[donnees["type_document"]]
        if tiers_detecte:
            donnees["tiers"] = tiers_detecte
        document.donnees_extraites = donnees
        db.commit()

        chrono = _executer_etape(
            "chrono", document_id,
            chrono_service.obtenir_ou_creer_chrono,
            db, document.cabinet_id, entreprise.id,
        )

        date_piece = donnees.get("date_piece")
        if date_piece:
            annee, mois = int(date_piece[:4]), int(date_piece[5:7])
        else:
            annee, mois = document.created_at.year, document.created_at.month

        document.entreprise_id = entreprise.id
        document.chrono_id = chrono.id
        document.annee = annee
        document.mois = mois
        document.categorie = donnees.get("categorie") or "divers"
        document.statut = StatutDocumentEnum.TRAITE
        db.commit()

        # --- MODIFICATION ICI : Aiguillage Banque vs Achats/Ventes ---
        if document.categorie == "banque":
            _executer_etape(
                "creation_mouvements_bancaires", document_id,
                accounting_service.creer_mouvements_bancaires,
                db, document,
            )
            logger.info("Document %s | Pipeline complet (RELEVÉ BANCAIRE) -- TRAITÉ", document_id)
        else:
            ecriture = _executer_etape(
                "creation_ecriture", document_id,
                accounting_service.creer_ecriture_depuis_document,
                db, document,
            )
            _executer_etape(
                "detection_doublon", document_id,
                anomaly_service.appliquer_detection_doublon,
                db, ecriture,
            )
            logger.info("Document %s | Pipeline complet (FACTURE/CNSS) -- TRAITÉ", document_id)

    except ErreurPipelineDefinitive as exc:
        db.rollback()
        logger.error("Document %s | Erreur définitive [%s] : %s", document_id, exc.code, exc)
        _marquer_erreur(db, document_id, str(exc), TypeErreurEnum.DEFINITIVE, exc.code)

    except Exception as exc:
        db.rollback()
        _marquer_erreur(db, document_id, str(exc), TypeErreurEnum.TRANSITOIRE, "TRANSIENT_ERROR")

        if self.request.retries >= self.max_retries:
            logger.error(
                "Document %s | Échec définitif après %s tentatives : %s",
                document_id, self.request.retries, exc,
            )
            return

        logger.warning(
            "Document %s | Tentative %s/%s échouée, retry programmé : %s",
            document_id, self.request.retries + 1, self.max_retries, exc,
        )
        raise self.retry(exc=exc)

    finally:
        db.close()