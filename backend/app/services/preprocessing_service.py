"""
app/services/preprocessing_service.py

Prétraitement léger (niveaux de gris + CLAHE), streamé page par page.

CORRECTIF CRITIQUE (22/07) : la version précédente cédait des tableaux
numpy directement en mémoire à PaddleOCR (_ocr.predict(image_np)).
Sur cette installation (PaddleOCR 3.7 / PaddlePaddle 3.3.1), cet appel
ne lève AUCUNE erreur mais renvoie systématiquement zéro texte détecté
-- confirmé par 3 documents de formats différents (png, png, jpeg) tous
en échec OCR_VIDE malgré des fichiers sources valides. Le chemin de
fichier (str), en revanche, est confirmé fonctionnel (c'est ce qui
avait permis d'extraire correctement "FACTURE #12345..." au Sprint 2).

On écrit donc chaque page prétraitée dans un fichier temporaire PNG
(coût de quelques millisecondes, négligeable), et on cède son CHEMIN
plutôt que le tableau numpy brut -- même contrat qu'au Sprint 2, avec
le nettoyage léger et le DPI réduit du correctif vitesse en plus.

Choix technique maintenu : PyMuPDF (fitz), pas pdf2image/Poppler.
"""
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Iterator

import cv2
import fitz  # PyMuPDF
import numpy as np

from app.core.exceptions import FichierIllisibleError

logger = logging.getLogger("comptaflow.preprocessing")

PDF_RENDER_DPI = 150
EXTENSIONS_IMAGE = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

DIMENSION_MAX_PIXELS = 1800  # plafond largeur/hauteur -- réduit la charge
                             # mémoire de PaddleOCR sur des images sources
                             # très grandes (ex: photo de téléphone)


def _limiter_taille_image(image_bgr: np.ndarray) -> np.ndarray:
    """
    Redimensionne l'image si sa plus grande dimension dépasse
    DIMENSION_MAX_PIXELS -- réduit la charge mémoire pour l'OCR sans
    perte de lisibilité significative pour du texte de facture standard.
    """
    hauteur, largeur = image_bgr.shape[:2]
    plus_grande_dimension = max(hauteur, largeur)
    if plus_grande_dimension <= DIMENSION_MAX_PIXELS:
        return image_bgr

    ratio = DIMENSION_MAX_PIXELS / plus_grande_dimension
    nouvelle_largeur = int(largeur * ratio)
    nouvelle_hauteur = int(hauteur * ratio)
    return cv2.resize(
        image_bgr, (nouvelle_largeur, nouvelle_hauteur),
        interpolation=cv2.INTER_AREA,
    )


def _nettoyer_page_rapide(image_bgr: np.ndarray) -> np.ndarray:
    """Nettoyage léger : redimensionnement + niveaux de gris + CLAHE."""
    t0 = time.perf_counter()
    image_bgr = _limiter_taille_image(image_bgr)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    contrastee = clahe.apply(gray)
    resultat = cv2.cvtColor(contrastee, cv2.COLOR_GRAY2BGR)
    t1 = time.perf_counter()
    logger.info("Prétraitement page (léger) : %.3fs", t1 - t0)
    return resultat


def generer_pages_pretraitees(chemin_fichier: str) -> Iterator[str]:
    """
    Point d'entrée principal, appelé par document_processing.py.

    Générateur : cède le CHEMIN (str) d'une page prétraitée à la fois,
    écrite dans un fichier temporaire PNG. C'est l'appelant
    (document_processing.py) qui doit nettoyer ces fichiers après
    usage via nettoyer_fichier_temporaire().
    """
    if not os.path.exists(chemin_fichier):
        raise FichierIllisibleError(f"Fichier introuvable : {chemin_fichier}")

    extension = os.path.splitext(chemin_fichier)[1].lower()
    dossier_temp = Path(tempfile.gettempdir()) / "comptaflow_ocr" / str(uuid.uuid4())
    dossier_temp.mkdir(parents=True, exist_ok=True)

    try:
        if extension == ".pdf":
            document_pdf = fitz.open(chemin_fichier)
            try:
                if document_pdf.page_count == 0:
                    raise ValueError("PDF sans pages détectées.")
                zoom = PDF_RENDER_DPI / 72
                matrice = fitz.Matrix(zoom, zoom)
                for index, page in enumerate(document_pdf):
                    pixmap = page.get_pixmap(matrix=matrice)
                    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )
                    if pixmap.n == 4:
                        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                    else:
                        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                    page_pretraitee = _nettoyer_page_rapide(image)
                    chemin_page = dossier_temp / f"page_{index:03d}.png"
                    cv2.imwrite(str(chemin_page), page_pretraitee)
                    yield str(chemin_page)
            finally:
                document_pdf.close()

        elif extension in EXTENSIONS_IMAGE:
            image = cv2.imread(chemin_fichier)
            if image is None:
                raise ValueError("Image corrompue ou format non lisible par OpenCV.")
            page_pretraitee = _nettoyer_page_rapide(image)
            chemin_page = dossier_temp / "page_000.png"
            cv2.imwrite(str(chemin_page), page_pretraitee)
            yield str(chemin_page)

        else:
            raise ValueError(f"Extension non supportée : {extension}")

    except FichierIllisibleError:
        raise
    except Exception as exc:
        raise FichierIllisibleError(f"Erreur de lecture du document : {exc}") from exc


def nettoyer_dossier_temporaire(dossier_racine: str = None) -> None:
    """
    Supprime tout le dossier temporaire comptaflow_ocr (tous documents
    confondus) -- utile en cas de nettoyage global. En usage normal,
    voir nettoyer_fichier_temporaire() pour un nettoyage par document.
    """
    import shutil
    cible = Path(dossier_racine) if dossier_racine else Path(tempfile.gettempdir()) / "comptaflow_ocr"
    if cible.exists():
        shutil.rmtree(cible, ignore_errors=True)


def nettoyer_fichier_temporaire(chemin_page: str) -> None:
    """
    Supprime UN fichier temporaire de page (et son dossier parent s'il
    devient vide). Appelée par document_processing.py après chaque
    page traitée, succès ou échec.
    """
    try:
        chemin = Path(chemin_page)
        dossier_parent = chemin.parent
        chemin.unlink(missing_ok=True)
        try:
            dossier_parent.rmdir()  # ne réussit que si le dossier est vide
        except OSError:
            pass
    except OSError:
        pass