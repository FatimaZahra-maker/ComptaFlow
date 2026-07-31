"""Orchestrateur Celery du traitement documentaire.

Le traitement des factures reste inchangé dans son principe : Vision Groq en
priorité, puis OCR/texte et cascade existante. Les relevés bancaires disposent
désormais d'une branche isolée qui traite toutes leurs pages et conserve chaque
ligne de transaction.
"""

from __future__ import annotations

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
    accounting_service,
    ai_service,
    anomaly_service,
    bank_statement_service,
    chrono_service,
    company_service,
    ocr_service,
    preprocessing_service,
    vision_service,
)
from app.services.document_classifier import detecter_type_document

logger = logging.getLogger("comptaflow.pipeline")

# Pour une facture, quelques pages suffisent pour identifier les champs.
MAX_PAGES_VISION_TENTEES = 3
# Pour un relevé bancaire, toutes les pages utiles doivent être traitées.
MAX_PAGES_RELEVE_BANCAIRE = 50


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
            "Document %s | Étape '%s' -- ÉCHEC après %.2fs",
            document_id,
            nom_etape,
            duree,
        )
        raise

    duree = time.perf_counter() - debut
    logger.info("Document %s | Étape '%s' -- OK en %.2fs", document_id, nom_etape, duree)
    return resultat


def _extraire_texte_ocr(document: Document) -> str:
    """Extrait tout le texte natif ou OCR de toutes les pages."""
    texte_natif = preprocessing_service.extraire_texte_natif_pdf(document.chemin_stockage)
    if texte_natif is not None:
        return texte_natif

    textes_pages: list[str] = []
    dernier_chemin_page: str | None = None

    try:
        for chemin_page in preprocessing_service.generer_pages_pretraitees(
            document.chemin_stockage
        ):
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


def _est_releve_bancaire(donnees: dict | None) -> bool:
    if not donnees:
        return False
    return (
        donnees.get("type_document") == "releve_bancaire"
        or donnees.get("categorie_document") == "releve_bancaire"
        or donnees.get("categorie") == "banque"
    )


def _tenter_vision_multi_pages(document: Document, document_id: str) -> dict | None:
    """Vision générique pour les factures, vision dédiée pour toute la Banque.

    Une fois la première page reconnue comme relevé bancaire, chaque page
    suivante est extraite par le service bancaire. Aucune déduplication n'est
    effectuée : deux opérations identiques imprimées restent deux opérations.
    """
    if not settings.GROQ_API_KEY:
        return None

    pages_tentees = 0
    mode_banque = False
    pages_bancaires: list[dict] = []
    dernier_chemin_page: str | None = None

    try:
        for chemin_page in preprocessing_service.generer_pages_pretraitees(
            document.chemin_stockage
        ):
            dernier_chemin_page = chemin_page
            pages_tentees += 1

            try:
                if mode_banque:
                    if pages_tentees > MAX_PAGES_RELEVE_BANCAIRE:
                        logger.warning(
                            "Document %s | Relevé limité à %s pages pour sécurité.",
                            document_id,
                            MAX_PAGES_RELEVE_BANCAIRE,
                        )
                        break

                    page_banque = _executer_etape(
                        f"extraction_banque_page_{pages_tentees}",
                        document_id,
                        bank_statement_service.extraire_page_depuis_image,
                        chemin_page,
                        pages_tentees,
                    )
                    if page_banque is not None:
                        pages_bancaires.append(page_banque)
                    continue

                # Comportement historique pour la première page exploitable.
                if pages_tentees > MAX_PAGES_VISION_TENTEES:
                    break

                donnees_vision = _executer_etape(
                    f"extraction_vision_page_{pages_tentees}",
                    document_id,
                    vision_service.extraire_et_classifier_depuis_image,
                    chemin_page,
                )

                if donnees_vision is None:
                    continue

                if _est_releve_bancaire(donnees_vision):
                    mode_banque = True
                    page_banque = _executer_etape(
                        f"extraction_banque_page_{pages_tentees}",
                        document_id,
                        bank_statement_service.extraire_page_depuis_image,
                        chemin_page,
                        pages_tentees,
                    )
                    if page_banque is not None:
                        pages_bancaires.append(page_banque)
                    continue

                # Facture/CNSS/TVA : on garde le comportement antérieur.
                return donnees_vision

            finally:
                preprocessing_service.nettoyer_fichier_temporaire(chemin_page)

    finally:
        if dernier_chemin_page is not None:
            preprocessing_service.nettoyer_dossier_document(dernier_chemin_page)

    if mode_banque and pages_bancaires:
        return bank_statement_service.normaliser_et_valider_releve(
            pages_bancaires,
            source="groq_vision_banque",
        )

    logger.warning(
        "Document %s | Vision indisponible/échouée sur %s page(s) -- "
        "repli extraction natif/PaddleOCR.",
        document_id,
        pages_tentees,
    )
    return None


def _extraire_donnees_par_vision_ou_ocr(
    document: Document,
    document_id: str,
) -> tuple[dict, str]:
    """Extrait les données sans modifier la cascade facture existante."""
    donnees_vision = _tenter_vision_multi_pages(document, document_id)
    if donnees_vision is not None:
        return donnees_vision, ""

    texte = _executer_etape(
        "ocr_ou_natif",
        document_id,
        _extraire_texte_ocr,
        document,
    )

    # Repli dédié Banque depuis tout le texte OCR. Cette branche est exécutée
    # seulement si le classifieur local reconnaît un relevé bancaire.
    if detecter_type_document(texte) == "releve_bancaire":
        donnees_banque = _executer_etape(
            "extraction_banque_texte",
            document_id,
            bank_statement_service.extraire_releve_depuis_texte,
            texte,
        )
        if donnees_banque is not None:
            return donnees_banque, texte

    # Toutes les autres catégories continuent à utiliser le service existant.
    donnees = _executer_etape(
        "extraction_donnees",
        document_id,
        ai_service.extraire_donnees,
        texte,
    )
    donnees.setdefault("source_extraction", "ocr_texte")
    return donnees, texte


def _marquer_erreur(
    db,
    document_id: str,
    message: str,
    type_erreur: TypeErreurEnum,
    error_code: str,
) -> None:
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
        document.message_erreur = None
        document.type_erreur = None
        document.error_code = None
        db.commit()

        donnees, texte = _extraire_donnees_par_vision_ou_ocr(document, document_id)
        document.texte_ocr = texte
        document.donnees_extraites = donnees
        db.commit()
        _log_ram("extraction", document_id)

        entreprise, direction, tiers_detecte = _executer_etape(
            "identification_entreprise",
            document_id,
            company_service.identifier_entreprise_et_direction,
            db,
            document.cabinet_id,
            donnees,
        )

        if direction is not None:
            donnees["categorie"] = direction
        elif donnees.get("type_document") in (
            "releve_bancaire",
            "avis_cnss",
            "avis_tva",
        ):
            donnees["categorie"] = {
                "releve_bancaire": "banque",
                "avis_cnss": "cnss",
                "avis_tva": "tva",
            }[donnees["type_document"]]

        if tiers_detecte:
            donnees["tiers"] = tiers_detecte

        document.donnees_extraites = dict(donnees)
        db.commit()

        chrono = _executer_etape(
            "chrono",
            document_id,
            chrono_service.obtenir_ou_creer_chrono,
            db,
            document.cabinet_id,
            entreprise.id,
        )

        date_piece = donnees.get("date_piece")
        if isinstance(date_piece, str) and len(date_piece) >= 7:
            try:
                annee, mois = int(date_piece[:4]), int(date_piece[5:7])
            except ValueError:
                annee, mois = document.created_at.year, document.created_at.month
        else:
            annee, mois = document.created_at.year, document.created_at.month

        document.entreprise_id = entreprise.id
        document.chrono_id = chrono.id
        document.annee = annee
        document.mois = mois
        document.categorie = donnees.get("categorie") or "divers"
        document.statut = StatutDocumentEnum.TRAITE
        db.commit()

        if str(getattr(document.categorie, "value", document.categorie)) == "banque":
            mouvements = _executer_etape(
                "creation_mouvements_bancaires",
                document_id,
                accounting_service.creer_mouvements_bancaires,
                db,
                document,
            )
            logger.info(
                "Document %s | Relevé bancaire traité : %s ligne(s) conservée(s), statut extraction=%s",
                document_id,
                len(mouvements),
                donnees.get("extraction_bancaire_statut", "inconnu"),
            )
        else:
            ecriture = _executer_etape(
                "creation_ecriture",
                document_id,
                accounting_service.creer_ecriture_depuis_document,
                db,
                document,
            )
            _executer_etape(
                "detection_doublon",
                document_id,
                anomaly_service.appliquer_detection_doublon,
                db,
                ecriture,
            )
            logger.info("Document %s | Pipeline facture/CNSS terminé.", document_id)

    except ErreurPipelineDefinitive as exc:
        db.rollback()
        logger.error("Document %s | Erreur définitive [%s] : %s", document_id, exc.code, exc)
        _marquer_erreur(db, document_id, str(exc), TypeErreurEnum.DEFINITIVE, exc.code)

    except Exception as exc:
        db.rollback()
        _marquer_erreur(
            db,
            document_id,
            str(exc),
            TypeErreurEnum.TRANSITOIRE,
            "TRANSIENT_ERROR",
        )

        if self.request.retries >= self.max_retries:
            logger.error(
                "Document %s | Échec définitif après %s tentatives : %s",
                document_id,
                self.request.retries,
                exc,
            )
            return

        logger.warning(
            "Document %s | Tentative %s/%s échouée, retry programmé : %s",
            document_id,
            self.request.retries + 1,
            self.max_retries,
            exc,
        )
        raise self.retry(exc=exc)

    finally:
        db.close()
