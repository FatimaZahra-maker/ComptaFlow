"""
app/services/preprocessing_service.py

Prétraitement léger (niveaux de gris + CLAHE), streamé page par page.

CORRECTIF CRITIQUE (course dossier temporaire) : la version précédente
supprimait le dossier parent dès qu'il devenait vide après le
nettoyage d'UNE page (nettoyer_fichier_temporaire -> rmdir()). Sur un
document multi-pages, le dossier est momentanément vide entre deux
pages (la page suivante n'est pas encore écrite) -- le rmdir()
réussissait alors et supprimait le dossier PENDANT que le générateur
s'apprêtait à y écrire la page suivante, causant un échec d'écriture
silencieux (cv2.imwrite ne lève pas d'exception, retourne juste False)
et donc un "fichier introuvable" en aval.

Correctif : nettoyer_fichier_temporaire() ne supprime plus QUE le
fichier, jamais le dossier parent. Le dossier entier n'est supprimé
qu'UNE SEULE FOIS, après que le générateur soit complètement épuisé
(ou interrompu), via nettoyer_dossier_document() -- appelée par
l'appelant (document_processing.py) dans un bloc try/finally englobant
toute la boucle, pas à chaque itération.

Choix technique maintenu : PyMuPDF (fitz), pas pdf2image/Poppler.
"""
import logging
import os
import shutil
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

DIMENSION_MAX_PIXELS = 1800

SEUIL_CARACTERES_TEXTE_NATIF = 30


# Tente d'extraire le texte directement depuis la structure du PDF
# (PDF généré numériquement, pas un scan) -- quelques millisecondes,
# aucun appel à l'OCR. Retourne None si le fichier n'est pas un PDF,
# ou si le texte trouvé est trop court pour être exploitable.
def extraire_texte_natif_pdf(chemin_fichier: str) -> str | None:
    if os.path.splitext(chemin_fichier)[1].lower() != ".pdf":
        return None

    try:
        document_pdf = fitz.open(chemin_fichier)
        try:
            morceaux = [page.get_text() for page in document_pdf]
        finally:
            document_pdf.close()
    except Exception as exc:
        logger.warning("Échec de l'extraction de texte natif PDF (%s) -- repli OCR.", exc)
        return None

    texte = "\n".join(morceaux).strip()
    if len(texte) < SEUIL_CARACTERES_TEXTE_NATIF:
        logger.info(
            "PDF sans couche texte exploitable (%d caractères trouvés) -- pipeline OCR requis.",
            len(texte),
        )
        return None

    logger.info("Texte natif PDF extrait directement (%d caractères) -- OCR sauté.", len(texte))
    return texte


# Redimensionne l'image si sa plus grande dimension dépasse
# DIMENSION_MAX_PIXELS -- réduit la charge mémoire pour l'OCR/vision
# sans perte de lisibilité significative pour du texte de facture.
def _limiter_taille_image(image_bgr: np.ndarray) -> np.ndarray:
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


# Nettoyage léger d'une page : redimensionnement + niveaux de gris +
# CLAHE (amélioration du contraste local, utile sur des scans ternes).
def _nettoyer_page_rapide(image_bgr: np.ndarray) -> np.ndarray:
    t0 = time.perf_counter()
    image_bgr = _limiter_taille_image(image_bgr)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    contrastee = clahe.apply(gray)
    resultat = cv2.cvtColor(contrastee, cv2.COLOR_GRAY2BGR)
    t1 = time.perf_counter()
    logger.info("Prétraitement page (léger) : %.3fs", t1 - t0)
    return resultat


# Générateur principal : cède le CHEMIN (str) d'une page prétraitée à
# la fois, écrite dans un fichier temporaire PNG à l'intérieur d'un
# dossier UNIQUE PAR DOCUMENT (créé une fois, réutilisé pour toutes
# les pages). L'appelant doit :
#   1. appeler nettoyer_fichier_temporaire(chemin_page) après CHAQUE
#      page traitée (supprime uniquement le fichier, jamais le dossier)
#   2. appeler nettoyer_dossier_document(chemin_page) UNE SEULE FOIS
#      après la fin complète de la boucle (succès, break, ou
#      exception), pour supprimer le dossier entier proprement.
def generer_pages_pretraitees(chemin_fichier: str) -> Iterator[str]:
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
                    ecrit = cv2.imwrite(str(chemin_page), page_pretraitee)
                    if not ecrit:
                        # Écriture silencieusement échouée (dossier
                        # supprimé entre-temps, disque plein, etc.) --
                        # on signale explicitement plutôt que de céder
                        # un chemin vers un fichier qui n'existe pas.
                        raise FichierIllisibleError(
                            f"Échec d'écriture de la page prétraitée : {chemin_page}"
                        )
                    yield str(chemin_page)
            finally:
                document_pdf.close()

        elif extension in EXTENSIONS_IMAGE:
            image = cv2.imread(chemin_fichier)
            if image is None:
                raise ValueError("Image corrompue ou format non lisible par OpenCV.")
            page_pretraitee = _nettoyer_page_rapide(image)
            chemin_page = dossier_temp / "page_000.png"
            ecrit = cv2.imwrite(str(chemin_page), page_pretraitee)
            if not ecrit:
                raise FichierIllisibleError(f"Échec d'écriture de la page prétraitée : {chemin_page}")
            yield str(chemin_page)

        else:
            raise ValueError(f"Extension non supportée : {extension}")

    except FichierIllisibleError:
        raise
    except Exception as exc:
        raise FichierIllisibleError(f"Erreur de lecture du document : {exc}") from exc


# Supprime tout le dossier temporaire comptaflow_ocr (tous documents
# confondus) -- nettoyage global, pas utilisée dans le flux normal.
def nettoyer_dossier_temporaire(dossier_racine: str = None) -> None:
    cible = Path(dossier_racine) if dossier_racine else Path(tempfile.gettempdir()) / "comptaflow_ocr"
    if cible.exists():
        shutil.rmtree(cible, ignore_errors=True)


# Supprime UN fichier temporaire de page -- UNIQUEMENT le fichier,
# JAMAIS le dossier parent (voir docstring du module pour la course
# évitée). Appelée par l'appelant après CHAQUE page traitée.
def nettoyer_fichier_temporaire(chemin_page: str) -> None:
    try:
        Path(chemin_page).unlink(missing_ok=True)
    except OSError:
        pass


# Supprime le DOSSIER ENTIER contenant les pages d'un document --
# appelée UNE SEULE FOIS par l'appelant, après la fin complète de la
# consommation du générateur (succès, arrêt anticipé, ou exception).
# Prend en argument n'importe quel chemin de page déjà obtenu (on
# remonte à son dossier parent), pour ne pas avoir à faire remonter
# séparément le chemin du dossier depuis le générateur.
def nettoyer_dossier_document(chemin_page_exemple: str) -> None:
    try:
        dossier = Path(chemin_page_exemple).parent
        if dossier.exists():
            shutil.rmtree(dossier, ignore_errors=True)
    except OSError:
        pass