"""
app/services/preprocessing_service.py

Prétraitement des documents avant Groq Vision / PaddleOCR.

Pipeline :

PDF / image
    ↓
conversion en image
    ↓
détection orientation 0 / 90 / 180 / 270
    ↓
rotation automatique
    ↓
correction légère de l'inclinaison
    ↓
redimensionnement
    ↓
niveaux de gris + CLAHE
    ↓
PNG temporaire
    ↓
Groq Vision / PaddleOCR

IMPORTANT :
- traitement page par page pour limiter la RAM ;
- PyMuPDF est utilisé pour les PDF ;
- aucune dépendance Tesseract ;
- modèle d'orientation chargé paresseusement ;
- aucune rotation n'est appliquée si la confiance est insuffisante.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import threading
import time
import uuid

from pathlib import Path
from typing import Any, Iterator

import cv2
import fitz
import numpy as np

from app.core.exceptions import FichierIllisibleError


logger = logging.getLogger("comptaflow.preprocessing")


# ============================================================
# CONFIGURATION
# ============================================================

PDF_RENDER_DPI = 150

EXTENSIONS_IMAGE = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
}

DIMENSION_MAX_PIXELS = 1800

SEUIL_CARACTERES_TEXTE_NATIF = 30

SEUIL_CONFIANCE_ORIENTATION = 0.60

# Petite inclinaison uniquement.
ANGLE_DESKEW_MAX = 7.0

# En dessous, correction inutile.
ANGLE_DESKEW_MIN = 0.35


# ============================================================
# MODÈLE D'ORIENTATION
# ============================================================

_modele_orientation = None

_verrou_chargement_orientation = threading.Lock()

_verrou_prediction_orientation = threading.Lock()


def _obtenir_modele_orientation():
    """
    Charge le modèle PaddleOCR spécialisé dans
    l'orientation des documents.

    Chargement lazy :
    uniquement lors du premier document image.
    """

    global _modele_orientation

    if _modele_orientation is None:

        with _verrou_chargement_orientation:

            if _modele_orientation is None:

                logger.info(
                    "Chargement du modèle "
                    "d'orientation documentaire..."
                )

                from paddleocr import (
                    DocImgOrientationClassification,
                )

                _modele_orientation = (
                    DocImgOrientationClassification(
                        model_name=(
                            "PP-LCNet_x1_0_doc_ori"
                        ),
                        device="cpu",
                        enable_mkldnn=False,
                        cpu_threads=2,
                    )
                )

                logger.info(
                    "Modèle d'orientation chargé."
                )

    return _modele_orientation


# ============================================================
# UTILITAIRES RÉSULTAT PADDLE
# ============================================================

def _vers_liste(
    valeur: Any,
) -> list:
    """
    Transforme une valeur Paddle/PaddleX
    en liste Python.
    """

    if valeur is None:
        return []

    if isinstance(
        valeur,
        np.ndarray,
    ):
        return valeur.tolist()

    if isinstance(
        valeur,
        (
            list,
            tuple,
        ),
    ):
        return list(valeur)

    return [valeur]


def _extraire_dict_resultat(
    resultat: Any,
) -> dict:
    """
    PaddleOCR / PaddleX peut retourner différents
    objets suivant la version.

    Cette fonction récupère les champs utiles
    quelle que soit la représentation.
    """

    if isinstance(
        resultat,
        dict,
    ):

        data = resultat

    else:

        data = {}

        for cle in (
            "label_names",
            "scores",
            "class_ids",
        ):

            try:
                valeur = resultat[cle]

            except Exception:
                valeur = None

            if valeur is not None:
                data[cle] = valeur

        if not data:

            try:

                json_value = getattr(
                    resultat,
                    "json",
                )

                if callable(
                    json_value
                ):
                    json_value = json_value()

                if isinstance(
                    json_value,
                    dict,
                ):
                    data = json_value

            except Exception:
                pass

    if (
        isinstance(data, dict)
        and isinstance(
            data.get("res"),
            dict,
        )
    ):

        data = data["res"]

    if not isinstance(
        data,
        dict,
    ):
        return {}

    return data


# ============================================================
# DÉTECTION ORIENTATION
# ============================================================

def _detecter_orientation(
    image_bgr: np.ndarray,
) -> tuple[int, float]:
    """
    Détecte l'orientation :

    0 / 90 / 180 / 270

    Retour :
        angle, confiance

    Une erreur ici ne doit jamais bloquer
    complètement le traitement du document.
    """

    try:

        modele = (
            _obtenir_modele_orientation()
        )

        with _verrou_prediction_orientation:

            resultats = modele.predict(
                image_bgr,
                batch_size=1,
            )

            premier = next(
                iter(resultats),
                None,
            )

        if premier is None:

            logger.warning(
                "Orientation : aucun résultat."
            )

            return 0, 0.0

        data = _extraire_dict_resultat(
            premier
        )

        labels = _vers_liste(
            data.get(
                "label_names"
            )
        )

        scores = _vers_liste(
            data.get(
                "scores"
            )
        )

        if not labels:

            logger.warning(
                "Orientation : label absent."
            )

            return 0, 0.0

        try:

            angle = int(
                str(
                    labels[0]
                )
                .replace(
                    "°",
                    "",
                )
                .strip()
            )

        except (
            TypeError,
            ValueError,
        ):

            logger.warning(
                "Orientation inconnue : %s",
                labels[0],
            )

            return 0, 0.0

        if angle not in {
            0,
            90,
            180,
            270,
        }:

            logger.warning(
                "Angle orientation non supporté : %s",
                angle,
            )

            return 0, 0.0

        confiance = 0.0

        if scores:

            try:

                confiance = float(
                    scores[0]
                )

            except (
                TypeError,
                ValueError,
            ):

                confiance = 0.0

        logger.info(
            (
                "Orientation détectée : "
                "%s° | confiance %.3f"
            ),
            angle,
            confiance,
        )

        return (
            angle,
            confiance,
        )

    except Exception as exc:

        logger.warning(
            (
                "Détection orientation "
                "indisponible : %s. "
                "Image conservée sans rotation."
            ),
            exc,
        )

        return 0, 0.0


# ============================================================
# CORRECTION ORIENTATION
# ============================================================

def _corriger_orientation(
    image_bgr: np.ndarray,
) -> np.ndarray:
    """
    Corrige automatiquement les rotations
    90 / 180 / 270 degrés.
    """

    angle, confiance = (
        _detecter_orientation(
            image_bgr
        )
    )

    if angle == 0:
        return image_bgr

    if (
        confiance
        < SEUIL_CONFIANCE_ORIENTATION
    ):

        logger.warning(
            (
                "Orientation %s° ignorée : "
                "confiance %.3f < %.2f"
            ),
            angle,
            confiance,
            SEUIL_CONFIANCE_ORIENTATION,
        )

        return image_bgr

    if angle == 90:

        image_corrigee = cv2.rotate(
            image_bgr,
            cv2.ROTATE_90_COUNTERCLOCKWISE,
        )

    elif angle == 180:

        image_corrigee = cv2.rotate(
            image_bgr,
            cv2.ROTATE_180,
        )

    elif angle == 270:

        image_corrigee = cv2.rotate(
            image_bgr,
            cv2.ROTATE_90_CLOCKWISE,
        )

    else:

        return image_bgr

    logger.info(
        (
            "Rotation automatique appliquée : "
            "%s° | confiance %.3f"
        ),
        angle,
        confiance,
    )

    return image_corrigee


# ============================================================
# DÉTECTION PETITE INCLINAISON
# ============================================================

def _calculer_angle_inclinaison(
    image_bgr: np.ndarray,
) -> float:
    """
    Détecte une petite inclinaison du document.

    CORRECTIF IMPORTANT :

    Selon OpenCV, HoughLinesP peut retourner :

        [[x1, y1, x2, y2]]

    ou :

        [x1, y1, x2, y2]

    On utilise donc reshape(-1) avant de lire les
    coordonnées.

    Cela corrige l'erreur :

        cannot unpack non-iterable numpy.int32 object
    """

    gray = cv2.cvtColor(
        image_bgr,
        cv2.COLOR_BGR2GRAY,
    )

    hauteur, largeur = (
        gray.shape[:2]
    )

    dimension_max = max(
        hauteur,
        largeur,
    )

    # --------------------------------------------------------
    # Réduction uniquement pour la détection
    # --------------------------------------------------------

    if dimension_max > 1200:

        ratio = (
            1200
            / dimension_max
        )

        nouvelle_largeur = max(
            1,
            int(
                largeur
                * ratio
            ),
        )

        nouvelle_hauteur = max(
            1,
            int(
                hauteur
                * ratio
            ),
        )

        gray_detection = cv2.resize(
            gray,
            (
                nouvelle_largeur,
                nouvelle_hauteur,
            ),
            interpolation=cv2.INTER_AREA,
        )

    else:

        gray_detection = gray

    # --------------------------------------------------------
    # LISSAGE + CONTOURS
    # --------------------------------------------------------

    blur = cv2.GaussianBlur(
        gray_detection,
        (
            3,
            3,
        ),
        0,
    )

    edges = cv2.Canny(
        blur,
        50,
        150,
        apertureSize=3,
    )

    largeur_detection = (
        gray_detection.shape[1]
    )

    longueur_min = max(
        80,
        int(
            largeur_detection
            * 0.20
        ),
    )

    # --------------------------------------------------------
    # LIGNES
    # --------------------------------------------------------

    lignes = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=70,
        minLineLength=longueur_min,
        maxLineGap=20,
    )

    if lignes is None:
        return 0.0

    angles: list[float] = []

    # ========================================================
    # CORRECTIF DU BUG OBSERVÉ DANS TES LOGS
    # ========================================================

    for ligne in lignes:

        # Fonctionne aussi bien avec :
        #
        # [[x1, y1, x2, y2]]
        #
        # que :
        #
        # [x1, y1, x2, y2]

        coordonnees = np.asarray(
            ligne
        ).reshape(-1)

        if (
            coordonnees.size
            < 4
        ):

            continue

        try:

            x1 = float(
                coordonnees[0]
            )

            y1 = float(
                coordonnees[1]
            )

            x2 = float(
                coordonnees[2]
            )

            y2 = float(
                coordonnees[3]
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        dx = (
            x2
            - x1
        )

        dy = (
            y2
            - y1
        )

        if (
            abs(dx)
            < 1e-9
        ):

            continue

        angle = float(
            np.degrees(
                np.arctan2(
                    dy,
                    dx,
                )
            )
        )

        # Ramène dans :
        #
        # -45° ... +45°

        while angle > 45:
            angle -= 90

        while angle < -45:
            angle += 90

        # On ne veut détecter ici
        # qu'une petite inclinaison.

        if (
            abs(angle)
            <= ANGLE_DESKEW_MAX
        ):

            angles.append(
                angle
            )

    if (
        len(angles)
        < 2
    ):

        return 0.0

    angle_final = float(
        np.median(
            angles
        )
    )

    return angle_final


# ============================================================
# ROTATION LIBRE
# ============================================================

def _rotation_angle_libre(
    image_bgr: np.ndarray,
    angle: float,
) -> np.ndarray:
    """
    Rotation légère en agrandissant le canvas
    pour éviter de couper les coins.
    """

    hauteur, largeur = (
        image_bgr.shape[:2]
    )

    centre = (
        largeur / 2.0,
        hauteur / 2.0,
    )

    matrice = (
        cv2.getRotationMatrix2D(
            centre,
            angle,
            1.0,
        )
    )

    cosinus = abs(
        matrice[
            0,
            0
        ]
    )

    sinus = abs(
        matrice[
            0,
            1
        ]
    )

    nouvelle_largeur = int(
        (
            hauteur
            * sinus
        )
        +
        (
            largeur
            * cosinus
        )
    )

    nouvelle_hauteur = int(
        (
            hauteur
            * cosinus
        )
        +
        (
            largeur
            * sinus
        )
    )

    matrice[
        0,
        2
    ] += (
        nouvelle_largeur
        / 2
        - centre[0]
    )

    matrice[
        1,
        2
    ] += (
        nouvelle_hauteur
        / 2
        - centre[1]
    )

    return cv2.warpAffine(
        image_bgr,
        matrice,
        (
            nouvelle_largeur,
            nouvelle_hauteur,
        ),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(
            255,
            255,
            255,
        ),
    )


# ============================================================
# CORRECTION DESKEW
# ============================================================

def _corriger_inclinaison(
    image_bgr: np.ndarray,
) -> np.ndarray:
    """
    Corrige seulement les petites inclinaisons.
    """

    angle = (
        _calculer_angle_inclinaison(
            image_bgr
        )
    )

    if (
        abs(angle)
        < ANGLE_DESKEW_MIN
    ):

        return image_bgr

    if (
        abs(angle)
        > ANGLE_DESKEW_MAX
    ):

        return image_bgr

    logger.info(
        (
            "Deskew automatique : "
            "inclinaison %.2f°"
        ),
        angle,
    )

    return _rotation_angle_libre(
        image_bgr,
        -angle,
    )


# ============================================================
# REDIMENSIONNEMENT
# ============================================================

def _limiter_taille_image(
    image_bgr: np.ndarray,
) -> np.ndarray:
    """
    Limite la plus grande dimension
    à DIMENSION_MAX_PIXELS.
    """

    hauteur, largeur = (
        image_bgr.shape[:2]
    )

    plus_grande_dimension = max(
        hauteur,
        largeur,
    )

    if (
        plus_grande_dimension
        <= DIMENSION_MAX_PIXELS
    ):

        return image_bgr

    ratio = (
        DIMENSION_MAX_PIXELS
        / plus_grande_dimension
    )

    nouvelle_largeur = max(
        1,
        int(
            largeur
            * ratio
        ),
    )

    nouvelle_hauteur = max(
        1,
        int(
            hauteur
            * ratio
        ),
    )

    return cv2.resize(
        image_bgr,
        (
            nouvelle_largeur,
            nouvelle_hauteur,
        ),
        interpolation=cv2.INTER_AREA,
    )


# ============================================================
# NETTOYAGE COMPLET D'UNE PAGE
# ============================================================

def _nettoyer_page_rapide(
    image_bgr: np.ndarray,
) -> np.ndarray:
    """
    Pipeline :

    orientation
        ↓
    deskew
        ↓
    redimensionnement
        ↓
    gris
        ↓
    contraste CLAHE
    """

    debut = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # 1. ORIENTATION
    # --------------------------------------------------------

    image_bgr = (
        _corriger_orientation(
            image_bgr
        )
    )

    # --------------------------------------------------------
    # 2. PETITE INCLINAISON
    # --------------------------------------------------------

    image_bgr = (
        _corriger_inclinaison(
            image_bgr
        )
    )

    # --------------------------------------------------------
    # 3. DIMENSIONS
    # --------------------------------------------------------

    image_bgr = (
        _limiter_taille_image(
            image_bgr
        )
    )

    # --------------------------------------------------------
    # 4. GRIS
    # --------------------------------------------------------

    gray = cv2.cvtColor(
        image_bgr,
        cv2.COLOR_BGR2GRAY,
    )

    # --------------------------------------------------------
    # 5. CONTRASTE
    # --------------------------------------------------------

    clahe = cv2.createCLAHE(
        clipLimit=1.5,
        tileGridSize=(
            8,
            8,
        ),
    )

    contrastee = (
        clahe.apply(
            gray
        )
    )

    resultat = cv2.cvtColor(
        contrastee,
        cv2.COLOR_GRAY2BGR,
    )

    duree = (
        time.perf_counter()
        - debut
    )

    logger.info(
        (
            "Prétraitement page terminé "
            "en %.3fs"
        ),
        duree,
    )

    return resultat


# ============================================================
# TEXTE NATIF PDF
# ============================================================

def extraire_texte_natif_pdf(
    chemin_fichier: str,
) -> str | None:
    """
    Si un PDF possède déjà une vraie couche texte,
    PyMuPDF peut récupérer le texte directement.

    Si ce n'est pas le cas :
        retourne None
        → PaddleOCR prend le relais.
    """

    extension = os.path.splitext(
        chemin_fichier
    )[1].lower()

    if extension != ".pdf":
        return None

    try:

        document_pdf = fitz.open(
            chemin_fichier
        )

        try:

            morceaux = [
                page.get_text()
                for page in document_pdf
            ]

        finally:

            document_pdf.close()

    except Exception as exc:

        logger.warning(
            (
                "Échec extraction texte natif "
                "PDF (%s) -- repli OCR."
            ),
            exc,
        )

        return None

    texte = (
        "\n".join(
            morceaux
        )
        .strip()
    )

    if (
        len(texte)
        < SEUIL_CARACTERES_TEXTE_NATIF
    ):

        logger.info(
            (
                "PDF sans couche texte exploitable "
                "(%d caractères)."
            ),
            len(texte),
        )

        return None

    logger.info(
        (
            "Texte natif PDF extrait "
            "(%d caractères)."
        ),
        len(texte),
    )

    return texte


# ============================================================
# GÉNÉRATION DES PAGES PRÉTRAITÉES
# ============================================================

def generer_pages_pretraitees(
    chemin_fichier: str,
) -> Iterator[str]:
    """
    Transforme un PDF ou une image
    en PNG prétraité page par page.

    Le PNG sera ensuite utilisé par :
    - Groq Vision
    - PaddleOCR
    """

    if not os.path.exists(
        chemin_fichier
    ):

        raise FichierIllisibleError(
            (
                "Fichier introuvable : "
                f"{chemin_fichier}"
            )
        )

    extension = os.path.splitext(
        chemin_fichier
    )[1].lower()

    dossier_temp = (
        Path(
            tempfile.gettempdir()
        )
        / "comptaflow_ocr"
        / str(
            uuid.uuid4()
        )
    )

    dossier_temp.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        # ====================================================
        # PDF
        # ====================================================

        if extension == ".pdf":

            document_pdf = fitz.open(
                chemin_fichier
            )

            try:

                if (
                    document_pdf.page_count
                    == 0
                ):

                    raise ValueError(
                        "PDF sans pages détectées."
                    )

                zoom = (
                    PDF_RENDER_DPI
                    / 72
                )

                matrice = fitz.Matrix(
                    zoom,
                    zoom,
                )

                for (
                    index,
                    page,
                ) in enumerate(
                    document_pdf
                ):

                    pixmap = (
                        page.get_pixmap(
                            matrix=matrice
                        )
                    )

                    image = np.frombuffer(
                        pixmap.samples,
                        dtype=np.uint8,
                    ).reshape(
                        pixmap.height,
                        pixmap.width,
                        pixmap.n,
                    )

                    if (
                        pixmap.n
                        == 4
                    ):

                        image = cv2.cvtColor(
                            image,
                            cv2.COLOR_RGBA2BGR,
                        )

                    else:

                        image = cv2.cvtColor(
                            image,
                            cv2.COLOR_RGB2BGR,
                        )

                    page_pretraitee = (
                        _nettoyer_page_rapide(
                            image
                        )
                    )

                    chemin_page = (
                        dossier_temp
                        / (
                            f"page_"
                            f"{index:03d}"
                            ".png"
                        )
                    )

                    succes = cv2.imwrite(
                        str(
                            chemin_page
                        ),
                        page_pretraitee,
                    )

                    if not succes:

                        raise OSError(
                            (
                                "Impossible d'écrire "
                                "la page temporaire."
                            )
                        )

                    yield str(
                        chemin_page
                    )

            finally:

                document_pdf.close()

        # ====================================================
        # IMAGE
        # ====================================================

        elif (
            extension
            in EXTENSIONS_IMAGE
        ):

            image = cv2.imread(
                chemin_fichier
            )

            if image is None:

                raise ValueError(
                    (
                        "Image corrompue ou "
                        "format non lisible "
                        "par OpenCV."
                    )
                )

            page_pretraitee = (
                _nettoyer_page_rapide(
                    image
                )
            )

            chemin_page = (
                dossier_temp
                / "page_000.png"
            )

            succes = cv2.imwrite(
                str(
                    chemin_page
                ),
                page_pretraitee,
            )

            if not succes:

                raise OSError(
                    (
                        "Impossible d'écrire "
                        "l'image temporaire."
                    )
                )

            yield str(
                chemin_page
            )

        else:

            raise ValueError(
                (
                    "Extension non supportée : "
                    f"{extension}"
                )
            )

    except FichierIllisibleError:
        raise

    except Exception as exc:

        raise FichierIllisibleError(
            (
                "Erreur de lecture "
                f"du document : {exc}"
            )
        ) from exc


# ============================================================
# NETTOYAGE TEMPORAIRE
# ============================================================

def nettoyer_fichier_temporaire(
    chemin_page: str,
) -> None:
    """
    Supprime une page temporaire.

    Supprime aussi son dossier
    s'il est devenu vide.
    """

    try:

        chemin = Path(
            chemin_page
        )

        dossier_parent = (
            chemin.parent
        )

        chemin.unlink(
            missing_ok=True
        )

        try:
            dossier_parent.rmdir()

        except OSError:
            pass

    except OSError:
        pass


def nettoyer_dossier_document(
    chemin_page: str,
) -> None:
    """
    Nettoyage de sécurité du dossier
    temporaire du document courant.
    """

    try:

        dossier = (
            Path(
                chemin_page
            ).parent
        )

        if dossier.exists():

            shutil.rmtree(
                dossier,
                ignore_errors=True,
            )

    except OSError:
        pass


def nettoyer_dossier_temporaire(
    dossier_racine: str | None = None,
) -> None:
    """
    Nettoyage global éventuel
    du dossier temporaire ComptaFlow.
    """

    if dossier_racine:

        cible = Path(
            dossier_racine
        )

    else:

        cible = (
            Path(
                tempfile.gettempdir()
            )
            / "comptaflow_ocr"
        )

    if cible.exists():

        shutil.rmtree(
            cible,
            ignore_errors=True,
        )