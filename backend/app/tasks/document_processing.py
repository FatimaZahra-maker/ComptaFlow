"""
app/tasks/document_processing.py

Orchestrateur Celery : prétraitement + OCR (RAM, streaming page par
page) + extraction (Groq -> Ollama direct -> regex, voir
ai_service.extraire_donnees) + identification entreprise/direction +
chrono + classement + écriture comptable + détection de doublon.

CHANGEMENT : l'extraction est maintenant TOUJOURS résolue de façon
SYNCHRONE dans le chemin critique (Groq d'abord, repli direct sur
Ollama si besoin, jamais de tâche différée) -- ai_enrichment.py n'est
plus appelée automatiquement ici. Le comptable voit toujours un
document déjà enrichi (ou au pire, ses champs regex) dès qu'il est
marqué TRAITÉ.
"""
import logging
import os
import time
import psutil
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.exceptions import ErreurPipelineDefinitive, OCRVideError
from app.models.document import Document
from app.models.enums import StatutDocumentEnum, TypeErreurEnum
from app.services import (
    preprocessing_service,
    ocr_service,
    ai_service,
    company_service,
    chrono_service,
    accounting_service,
    anomaly_service,
)

logger = logging.getLogger("comptaflow.pipeline")


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
    textes_pages: list[str] = []
    for chemin_page in preprocessing_service.generer_pages_pretraitees(document.chemin_stockage):
        try:
            texte_page = ocr_service.extraire_texte_page(chemin_page)
            if texte_page.strip():
                textes_pages.append(texte_page)
        finally:
            preprocessing_service.nettoyer_fichier_temporaire(chemin_page)
    texte_final = "\n".join(textes_pages)
    if not texte_final.strip():
        raise OCRVideError(
            "L'OCR n'a extrait aucun texte du document (fichier vide, "
            "illisible, ou image trop dégradée)."
        )
    return texte_final


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

        # --- 1. Prétraitement + OCR ---
        texte = _executer_etape("ocr", document_id, _extraire_texte_ocr, document)
        document.texte_ocr = texte
        db.commit()
        _log_ram("ocr", document_id)

        # --- 2. Extraction : Groq -> Ollama direct -> regex (voir ai_service) ---
        donnees = _executer_etape(
            "extraction_donnees", document_id,
            ai_service.extraire_donnees, texte,
        )
        document.donnees_extraites = donnees
        db.commit()

        # --- 3. Identification entreprise + direction achats/ventes ---
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

        # --- 4. Chrono ---
        chrono = _executer_etape(
            "chrono", document_id,
            chrono_service.obtenir_ou_creer_chrono,
            db, document.cabinet_id, entreprise.id,
        )

        # --- 5. Classement final ---
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

        # --- 6. Écriture comptable + détection de doublon ---
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

        logger.info("Document %s | Pipeline complet -- TRAITÉ", document_id)

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