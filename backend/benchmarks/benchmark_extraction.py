from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil


# ============================================================
# IMPORT DU BACKEND
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.services import (
    ai_service,
    bank_statement_service,
    ocr_service,
    preprocessing_service,
    vision_service,
)

from app.tasks import document_processing


# ============================================================
# CONSTANTES
# ============================================================

OCTETS_PAR_MO = 1024 * 1024
INTERVALLE_RAM_SECONDES = 0.05


# ============================================================
# OUTILS
# ============================================================

def ram_mo() -> float:
    return (
        psutil.Process(os.getpid())
        .memory_info()
        .rss
        / OCTETS_PAR_MO
    )


def taille_mo(path: str | Path) -> float:
    try:
        return Path(path).stat().st_size / OCTETS_PAR_MO
    except OSError:
        return 0.0


def serialiser(objet: Any) -> Any:
    if isinstance(objet, Path):
        return str(objet)

    return str(objet)


# ============================================================
# DIAGNOSTIC
# ============================================================

class Diagnostic:

    def __init__(self) -> None:
        self.etapes: list[dict[str, Any]] = []
        self._originaux: list[
            tuple[Any, str, Any]
        ] = []

        self._lock = threading.Lock()


    def ajouter(
        self,
        nom: str,
        debut: float,
        ram_avant: float,
        **extras: Any,
    ) -> None:

        entree = {
            "etape": nom,

            "duree_secondes": round(
                time.perf_counter() - debut,
                3,
            ),

            "ram_avant_mo": round(
                ram_avant,
                1,
            ),

            "ram_apres_mo": round(
                ram_mo(),
                1,
            ),
        }

        entree.update(extras)

        with self._lock:
            self.etapes.append(entree)

        print(
            f"[DIAG] {nom:<34} "
            f"{entree['duree_secondes']:>8.3f}s | "
            f"RAM "
            f"{entree['ram_avant_mo']:>7.1f}"
            f" -> "
            f"{entree['ram_apres_mo']:>7.1f} MB"
        )


    def remplacer(
        self,
        module: Any,
        nom: str,
        nouveau: Any,
    ) -> None:

        original = getattr(
            module,
            nom,
        )

        self._originaux.append(
            (
                module,
                nom,
                original,
            )
        )

        setattr(
            module,
            nom,
            nouveau,
        )


    def restaurer(self) -> None:

        for module, nom, original in reversed(
            self._originaux
        ):

            setattr(
                module,
                nom,
                original,
            )

        self._originaux.clear()


    def installer(self) -> None:

        # ====================================================
        # 1. PRÉTRAITEMENT
        # ====================================================

        original_generer = (
            preprocessing_service
            .generer_pages_pretraitees
        )


        def generer_pages_instrumente(
            chemin_fichier: str,
        ):

            generateur = original_generer(
                chemin_fichier
            )

            index = 0

            while True:

                debut = time.perf_counter()
                avant = ram_mo()

                try:
                    chemin_page = next(
                        generateur
                    )

                except StopIteration:
                    break

                index += 1

                largeur = None
                hauteur = None

                try:
                    from PIL import Image

                    with Image.open(
                        chemin_page
                    ) as image:

                        largeur, hauteur = (
                            image.size
                        )

                except Exception:
                    pass


                self.ajouter(
                    f"pretraitement_page_{index}",
                    debut,
                    avant,

                    fichier_temp_mo=round(
                        taille_mo(
                            chemin_page
                        ),
                        3,
                    ),

                    largeur_px=largeur,
                    hauteur_px=hauteur,
                )

                yield chemin_page


        self.remplacer(
            preprocessing_service,
            "generer_pages_pretraitees",
            generer_pages_instrumente,
        )


        # ====================================================
        # 2. ENCODAGE BASE64 POUR GROQ VISION
        # ====================================================

        original_encoder_vision = (
            vision_service
            ._encoder_image_base64
        )


        def encoder_vision_instrumente(
            chemin_image: str,
        ) -> str:

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = (
                original_encoder_vision(
                    chemin_image
                )
            )

            self.ajouter(
                "vision_encodage_base64",
                debut,
                avant,

                fichier_image_mo=round(
                    taille_mo(
                        chemin_image
                    ),
                    3,
                ),

                base64_mo=round(
                    len(
                        resultat.encode(
                            "ascii"
                        )
                    )
                    / OCTETS_PAR_MO,
                    3,
                ),
            )

            return resultat


        self.remplacer(
            vision_service,
            "_encoder_image_base64",
            encoder_vision_instrumente,
        )


        # ====================================================
        # 3. GROQ VISION
        # ====================================================

        original_vision = (
            vision_service
            .extraire_et_classifier_depuis_image
        )


        def vision_instrumentee(
            chemin_image: str,
        ):

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = original_vision(
                chemin_image
            )

            self.ajouter(
                "groq_vision_total",
                debut,
                avant,

                resultat_recu=(
                    resultat is not None
                ),
            )

            return resultat


        self.remplacer(
            vision_service,
            "extraire_et_classifier_depuis_image",
            vision_instrumentee,
        )


        # ====================================================
        # 4. CHARGEMENT PADDLEOCR
        # ====================================================

        original_obtenir_ocr = (
            ocr_service
            ._obtenir_ocr
        )


        def obtenir_ocr_instrumente():

            etait_deja_charge = (
                getattr(
                    ocr_service,
                    "_ocr",
                    None,
                )
                is not None
            )

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = (
                original_obtenir_ocr()
            )

            if not etait_deja_charge:

                self.ajouter(
                    "paddle_chargement_modele",
                    debut,
                    avant,
                )

            return resultat


        self.remplacer(
            ocr_service,
            "_obtenir_ocr",
            obtenir_ocr_instrumente,
        )


        # ====================================================
        # 5. OCR DE LA PAGE
        # ====================================================

        original_ocr_page = (
            ocr_service
            .extraire_texte_page
        )


        def ocr_page_instrumentee(
            chemin_image: str,
            timeout_sec: int = (
                ocr_service
                .TIMEOUT_PAR_PAGE_SECONDES
            ),
        ) -> str:

            debut = time.perf_counter()
            avant = ram_mo()

            texte = original_ocr_page(
                chemin_image,
                timeout_sec=timeout_sec,
            )

            self.ajouter(
                "paddle_ocr_page",
                debut,
                avant,

                caracteres=len(
                    texte or ""
                ),
            )

            return texte


        self.remplacer(
            ocr_service,
            "extraire_texte_page",
            ocr_page_instrumentee,
        )


        # ====================================================
        # 6. EXTRACTION BANQUE DEPUIS TEXTE OCR
        # ====================================================

        original_banque_texte = (
            bank_statement_service
            .extraire_releve_depuis_texte
        )


        def banque_texte_instrumentee(
            texte: str,
        ):

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = (
                original_banque_texte(
                    texte
                )
            )

            self.ajouter(
                "groq_texte_banque_total",
                debut,
                avant,

                caracteres_entree=len(
                    texte or ""
                ),

                resultat_recu=(
                    resultat is not None
                ),
            )

            return resultat


        self.remplacer(
            bank_statement_service,
            "extraire_releve_depuis_texte",
            banque_texte_instrumentee,
        )


        # ====================================================
        # 7. VISION BANCAIRE DÉDIÉE
        # ====================================================

        original_banque_image = (
            bank_statement_service
            .extraire_page_depuis_image
        )


        def banque_image_instrumentee(
            path: str,
            page_number: int,
        ):

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = (
                original_banque_image(
                    path,
                    page_number,
                )
            )

            self.ajouter(
                f"groq_vision_banque_page_"
                f"{page_number}",

                debut,
                avant,

                fichier_image_mo=round(
                    taille_mo(path),
                    3,
                ),

                resultat_recu=(
                    resultat is not None
                ),
            )

            return resultat


        self.remplacer(
            bank_statement_service,
            "extraire_page_depuis_image",
            banque_image_instrumentee,
        )


        # ====================================================
        # 8. IA GÉNÉRIQUE
        # ====================================================

        original_ai = (
            ai_service
            .extraire_donnees
        )


        def ai_instrumentee(
            texte: str,
        ):

            debut = time.perf_counter()
            avant = ram_mo()

            resultat = original_ai(
                texte
            )

            self.ajouter(
                "extraction_ia_generique_total",
                debut,
                avant,

                caracteres_entree=len(
                    texte or ""
                ),
            )

            return resultat


        self.remplacer(
            ai_service,
            "extraire_donnees",
            ai_instrumentee,
        )


# ============================================================
# MONITORING GLOBAL RAM
# ============================================================

def surveiller_pic_ram(
    stop_event: threading.Event,
    mesure: dict[str, float],
) -> None:

    processus = psutil.Process(
        os.getpid()
    )

    while not stop_event.is_set():

        try:

            valeur = (
                processus
                .memory_info()
                .rss
                / OCTETS_PAR_MO
            )

            mesure["pic_ram_mo"] = max(
                mesure["pic_ram_mo"],
                valeur,
            )

        except psutil.Error:
            pass

        stop_event.wait(
            INTERVALLE_RAM_SECONDES
        )


# ============================================================
# BENCHMARK
# ============================================================

def benchmarker_document(
    chemin_fichier: Path,
) -> dict[str, Any]:

    if (
        not chemin_fichier.exists()
        or not chemin_fichier.is_file()
    ):

        raise FileNotFoundError(
            f"Fichier introuvable : "
            f"{chemin_fichier}"
        )


    gc.collect()

    ram_initiale = ram_mo()

    mesure_ram = {
        "pic_ram_mo": ram_initiale,
    }


    stop_event = threading.Event()


    thread_ram = threading.Thread(
        target=surveiller_pic_ram,
        args=(
            stop_event,
            mesure_ram,
        ),
        daemon=True,
    )


    diagnostic = Diagnostic()

    diagnostic.installer()


    faux_document = SimpleNamespace(
        chemin_stockage=str(
            chemin_fichier.resolve()
        )
    )


    document_id = (
        f"diagnostic-"
        f"{chemin_fichier.stem}"
    )


    debut_total = time.perf_counter()

    thread_ram.start()


    try:

        donnees, texte_ocr = (
            document_processing
            ._extraire_donnees_par_vision_ou_ocr(
                faux_document,
                document_id,
            )
        )

        succes = True
        erreur = None


    except Exception as exc:

        donnees = {}
        texte_ocr = ""

        succes = False

        erreur = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )


    finally:

        stop_event.set()

        thread_ram.join(
            timeout=1.0
        )

        diagnostic.restaurer()


    duree_totale = (
        time.perf_counter()
        - debut_total
    )


    ram_finale = ram_mo()


    return {

        "timestamp":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "fichier":
            str(
                chemin_fichier.resolve()
            ),

        "nom_fichier":
            chemin_fichier.name,

        "taille_originale_mo":
            round(
                taille_mo(
                    chemin_fichier
                ),
                3,
            ),

        "succes":
            succes,

        "erreur":
            erreur,

        "duree_totale_secondes":
            round(
                duree_totale,
                3,
            ),

        "ram_initiale_mo":
            round(
                ram_initiale,
                1,
            ),

        "pic_ram_mo":
            round(
                mesure_ram[
                    "pic_ram_mo"
                ],
                1,
            ),

        "augmentation_pic_ram_mo":
            round(
                max(
                    0.0,
                    mesure_ram[
                        "pic_ram_mo"
                    ]
                    - ram_initiale,
                ),
                1,
            ),

        "ram_finale_mo":
            round(
                ram_finale,
                1,
            ),

        "longueur_texte_ocr":
            len(
                texte_ocr or ""
            ),

        "source_extraction":
            donnees.get(
                "source_extraction",
                "non_precisee",
            ),

        "type_document_detecte":
            (
                donnees.get(
                    "type_document"
                )
                or donnees.get(
                    "categorie_document"
                )
                or donnees.get(
                    "categorie"
                )
                or "non_detecte"
            ),

        "diagnostic_etapes":
            diagnostic.etapes,

        "donnees_extraites":
            donnees,
    }


# ============================================================
# SAUVEGARDE
# ============================================================

def sauvegarder(
    resultat: dict[str, Any],
    dossier: Path,
) -> Path:

    dossier.mkdir(
        parents=True,
        exist_ok=True,
    )


    nom = Path(
        resultat["nom_fichier"]
    ).stem


    horodatage = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )


    sortie = (
        dossier
        / f"{horodatage}_"
          f"{nom}_diagnostic.json"
    )


    sortie.write_text(
        json.dumps(
            resultat,
            ensure_ascii=False,
            indent=2,
            default=serialiser,
        ),
        encoding="utf-8",
    )


    return sortie


# ============================================================
# AFFICHAGE
# ============================================================

def afficher_resume(
    resultat: dict[str, Any],
    sortie: Path,
) -> None:

    print(
        "\n"
        + "=" * 78
    )

    print(
        "COMPTAFLOW - DIAGNOSTIC EXTRACTION"
    )

    print(
        "=" * 78
    )


    print(
        f"Fichier           : "
        f"{resultat['nom_fichier']}"
    )

    print(
        f"Taille originale  : "
        f"{resultat['taille_originale_mo']} MB"
    )

    print(
        f"Succès            : "
        f"{'OUI' if resultat['succes'] else 'NON'}"
    )

    print(
        f"Type              : "
        f"{resultat['type_document_detecte']}"
    )

    print(
        f"Source            : "
        f"{resultat['source_extraction']}"
    )

    print(
        f"Temps total       : "
        f"{resultat['duree_totale_secondes']} s"
    )

    print(
        f"RAM initiale      : "
        f"{resultat['ram_initiale_mo']} MB"
    )

    print(
        f"Pic RAM           : "
        f"{resultat['pic_ram_mo']} MB"
    )

    print(
        f"Hausse pic RAM    : "
        f"{resultat['augmentation_pic_ram_mo']} MB"
    )

    print(
        f"RAM finale        : "
        f"{resultat['ram_finale_mo']} MB"
    )


    print(
        "-" * 78
    )

    print(
        "DÉTAIL DES ÉTAPES"
    )


    for etape in resultat[
        "diagnostic_etapes"
    ]:

        extras = []

        if "fichier_temp_mo" in etape:

            extras.append(
                f"temp="
                f"{etape['fichier_temp_mo']}MB"
            )


        if "base64_mo" in etape:

            extras.append(
                f"base64="
                f"{etape['base64_mo']}MB"
            )


        if "caracteres" in etape:

            extras.append(
                f"texte="
                f"{etape['caracteres']} chars"
            )


        if "resultat_recu" in etape:

            extras.append(
                "résultat="
                + (
                    "oui"
                    if etape[
                        "resultat_recu"
                    ]
                    else "non"
                )
            )


        suffixe = (
            " | "
            + ", ".join(extras)
            if extras
            else ""
        )


        print(
            f"{etape['etape']:<34} "
            f"{etape['duree_secondes']:>8.3f}s | "
            f"RAM "
            f"{etape['ram_avant_mo']:>7.1f}"
            f"->"
            f"{etape['ram_apres_mo']:>7.1f} MB"
            f"{suffixe}"
        )


    print(
        "-" * 78
    )


    if resultat["erreur"]:

        print(
            f"Erreur            : "
            f"{resultat['erreur']}"
        )


    print(
        f"JSON diagnostic   : "
        f"{sortie}"
    )

    print(
        "=" * 78
    )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Diagnostic détaillé du pipeline "
            "d'extraction ComptaFlow."
        )
    )


    parser.add_argument(
        "--file",
        required=True,
        help=(
            "Chemin du document à tester."
        ),
    )


    parser.add_argument(
        "--results-dir",
        default=str(
            Path(__file__)
            .resolve()
            .parent
            / "results"
        ),
        help=(
            "Dossier de sortie JSON."
        ),
    )


    args = parser.parse_args()


    resultat = benchmarker_document(
        Path(
            args.file
        ).expanduser()
    )


    sortie = sauvegarder(
        resultat,
        Path(
            args.results_dir
        ).expanduser(),
    )


    afficher_resume(
        resultat,
        sortie,
    )


    return (
        0
        if resultat["succes"]
        else 1
    )


if __name__ == "__main__":

    raise SystemExit(
        main()
    )