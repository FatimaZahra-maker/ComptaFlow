"""
app/services/ocr_service.py

PaddleOCR dans un THREAD dédié, protégé par un timeout cross-platform
via ThreadPoolExecutor, avec CHARGEMENT PARESSEUX (lazy singleton).

CORRECTIF (retour aux modèles par défaut) : les modèles "mobile"
(text_detection_model_name="PP-OCRv6_mobile_det" etc.) échouent sur
cette installation avec "No engine bindings registered for model
'PP-OCRv6_mobile_det'" -- le moteur d'inférence pour cette variante
n'est pas correctement enregistré ici. Les modèles PAR DÉFAUT (sans
nom explicite, variante "medium") sont ceux dont le fonctionnement a
été confirmé en conditions réelles (test manuel isolé ayant extrait
correctement le texte d'une facture). On revient donc dessus --
l'optimisation vitesse "mobile" est abandonnée tant qu'elle n'aura pas
été validée par un test manuel isolé équivalent, AVANT réintégration
dans le pipeline complet.

HISTORIQUE DES ARCHITECTURES DE CONCURRENCE TESTÉES (pour ne pas
refaire les mêmes erreurs) :
1. Singleton module-level -> double empreinte RAM (API + worker).
2. ProcessPoolExecutor -> échec 100% sous Windows (spawn + Celery
   --pool=solo incompatibles).
3. Sous-processus persistant stdin/stdout -> échec 100% (protocole
   jamais fonctionnel).
Architecture retenue : thread + verrou + chargement paresseux -- seule
architecture ayant un succès confirmé en conditions réelles.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger("comptaflow.ocr_service")

# --- MODIFICATION ICI : 60 -> 300 (5 minutes) pour laisser le temps au CPU d'analyser la page ---
TIMEOUT_PAR_PAGE_SECONDES = 300

_ocr = None
_verrou_chargement = threading.Lock()
_verrou_ocr = threading.Lock()


# Charge PaddleOCR au premier appel uniquement (lazy singleton),
# protégé par un verrou pour éviter un double chargement si deux
# threads y accèdent au même instant. Utilise les modèles PAR DÉFAUT
# (pas de nom explicite -- variante "medium", confirmée fonctionnelle).
def _obtenir_ocr():
    global _ocr
    if _ocr is None:
        with _verrou_chargement:
            if _ocr is None:
                logger.info("Chargement de PaddleOCR (modèles par défaut, premier appel)...")
                from paddleocr import PaddleOCR
                _ocr = PaddleOCR(
                    lang="fr",
                    enable_mkldnn=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
                logger.info("PaddleOCR chargé (modèles par défaut).")
    return _ocr


# Appel bloquant réel à PaddleOCR, protégé par le verrou global --
# sérialise les appels réels au modèle partagé pour éviter un accès
# concurrent si un thread précédent a timeout mais tourne encore en
# arrière-plan.
def _predict_page_verrouille(chemin_image: str) -> str:
    ocr = _obtenir_ocr()
    with _verrou_ocr:
        resultats = ocr.predict(chemin_image)

    lignes: list[str] = []
    for page in resultats:
        if isinstance(page, dict):
            textes = page.get("rec_texts", [])
        else:
            try:
                textes = page["rec_texts"]
            except Exception:
                textes = []
        lignes.extend(textes)

    return "\n".join(lignes)


# Extrait le texte d'UNE page (fichier déjà prétraité), protégé par un
# timeout cross-platform. Le premier appel inclut le chargement du
# modèle.
def extraire_texte_page(chemin_image: str, timeout_sec: int = TIMEOUT_PAR_PAGE_SECONDES) -> str:
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(_predict_page_verrouille, chemin_image)
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeoutError:
            logger.error("Timeout OCR (%ss dépassées) -- page ignorée.", timeout_sec)
            return ""
    except Exception as exc:
        logger.error("Échec OCR inattendu sur une page : %s", exc)
        return ""
    finally:
        executor.shutdown(wait=False)