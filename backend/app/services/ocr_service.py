"""
app/services/ocr_service.py

Gère un sous-processus OCR PERSISTANT (ocr_worker_standalone.py, à la
racine de backend/), lancé une seule fois puis réutilisé pour toutes
les pages/documents suivants -- PaddleOCR ne recharge son modèle
qu'une fois, pas à chaque appel (voir la docstring de
ocr_worker_standalone.py pour le détail du protocole et le pourquoi).

Communication ligne par ligne (stdin/stdout), avec un thread dédié à
la lecture de stdout (nécessaire car stdout.readline() est bloquant et
ne supporte pas nativement un timeout multi-plateforme sous Windows).
Si le process ne répond pas dans le délai imparti, il est tué de force
(process.kill()) -- jamais abandonné en arrière-plan -- et un nouveau
process persistant sera relancé (et rechargera le modèle une fois) au
prochain appel.
"""
import json
import logging
import queue
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger("comptaflow.ocr_service")

TIMEOUT_PAR_PAGE_SECONDES = 60
TIMEOUT_DEMARRAGE_MODELE_SECONDES = 90  # premier chargement du modèle, plus long que l'OCR d'une page

_CHEMIN_SCRIPT_WORKER = Path(__file__).resolve().parent.parent.parent / "ocr_worker_standalone.py"


class _ProcessOCRPersistant:
    """
    Encapsule le sous-processus OCR persistant, son thread de lecture
    de stdout, et la logique de (re)démarrage. Une seule instance
    partagée par tous les appels (_process_partage, plus bas).
    """

    def __init__(self):
        self._processus: subprocess.Popen | None = None
        self._file_sortie: queue.Queue[str] = queue.Queue()
        self._thread_lecture: threading.Thread | None = None
        self._verrou = threading.Lock()

    def _lire_stdout_en_continu(self, processus: subprocess.Popen) -> None:
        """Tourne dans un thread dédié : lit stdout ligne par ligne et
        alimente la queue. S'arrête quand le process meurt (stdout se
        ferme, readline() renvoie '')."""
        for ligne in processus.stdout:
            self._file_sortie.put(ligne)

    def _demarrer_processus(self) -> bool:
        """Lance le sous-processus persistant et attend son signal
        'ready' (modèle chargé). Retourne False si le démarrage échoue
        ou timeout."""
        if not _CHEMIN_SCRIPT_WORKER.exists():
            logger.error("Script OCR autonome introuvable : %s", _CHEMIN_SCRIPT_WORKER)
            return False

        self._processus = subprocess.Popen(
            [sys.executable, str(_CHEMIN_SCRIPT_WORKER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # ligne par ligne
        )

        # Vide toute donnée résiduelle d'un précédent process mort.
        while not self._file_sortie.empty():
            try:
                self._file_sortie.get_nowait()
            except queue.Empty:
                break

        self._thread_lecture = threading.Thread(
            target=self._lire_stdout_en_continu, args=(self._processus,), daemon=True
        )
        self._thread_lecture.start()

        logger.info("Process OCR persistant démarré (PID %s), chargement du modèle en cours...", self._processus.pid)
        try:
            ligne = self._file_sortie.get(timeout=TIMEOUT_DEMARRAGE_MODELE_SECONDES)
        except queue.Empty:
            logger.error("Timeout au chargement du modèle OCR (%ss) -- process tué.", TIMEOUT_DEMARRAGE_MODELE_SECONDES)
            self._tuer_processus()
            return False

        try:
            reponse = json.loads(ligne)
        except json.JSONDecodeError:
            logger.error("Réponse de démarrage OCR illisible : %r", ligne)
            self._tuer_processus()
            return False

        if not reponse.get("ready"):
            logger.error("Le process OCR n'a pas signalé 'ready' : %s", reponse.get("error"))
            self._tuer_processus()
            return False

        logger.info("Process OCR persistant prêt (modèle chargé).")
        return True

    def _tuer_processus(self) -> None:
        if self._processus is not None:
            try:
                self._processus.kill()
                self._processus.wait(timeout=5)
            except Exception:
                pass
        self._processus = None

    def _processus_vivant(self) -> bool:
        return self._processus is not None and self._processus.poll() is None

    def extraire(self, chemin_image: str, timeout_sec: int) -> str:
        with self._verrou:
            if not self._processus_vivant():
                if not self._demarrer_processus():
                    return ""

            try:
                self._processus.stdin.write(chemin_image + "\n")
                self._processus.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                logger.error("Écriture vers le process OCR échouée (%s) -- process considéré mort.", exc)
                self._tuer_processus()
                return ""

            try:
                ligne = self._file_sortie.get(timeout=timeout_sec)
            except queue.Empty:
                logger.error(
                    "Timeout OCR (%ss dépassées) -- process OCR (PID %s) tué de force. "
                    "Un nouveau process sera relancé au prochain appel (rechargera le modèle une fois).",
                    timeout_sec, self._processus.pid if self._processus else "?",
                )
                self._tuer_processus()
                return ""

            try:
                reponse = json.loads(ligne)
            except json.JSONDecodeError:
                logger.error("Réponse OCR illisible : %r", ligne)
                return ""

            if not reponse.get("ok"):
                logger.error("OCR échoué sur '%s' : %s", chemin_image, reponse.get("error"))
                return ""

            return reponse.get("text", "")


_process_partage = _ProcessOCRPersistant()


def extraire_texte_page(chemin_image: str, timeout_sec: int = TIMEOUT_PAR_PAGE_SECONDES) -> str:
    return _process_partage.extraire(chemin_image, timeout_sec)