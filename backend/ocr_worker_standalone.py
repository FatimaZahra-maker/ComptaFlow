"""
backend/ocr_worker_standalone.py

Serveur OCR PERSISTANT, lancé UNE SEULE FOIS en sous-processus par
app/services/ocr_service.py (subprocess.Popen), et gardé vivant entre
tous les appels -- PaddleOCR ne charge son modèle qu'UNE fois au
démarrage de ce script, pas à chaque page traitée.

PROTOCOLE (ligne par ligne sur stdin/stdout) :
- Le process parent écrit un chemin d'image, suivi de "\n", sur stdin.
- Ce script lit la ligne, exécute l'OCR, écrit UNE ligne JSON sur
  stdout : {"ok": true, "text": "..."} ou {"ok": false, "error": "..."}.
  JSON est utilisé (et non du texte brut) car le texte OCR peut
  contenir des retours à la ligne -- JSON les échappe proprement en
  une seule ligne de sortie, sans ambiguïté de délimitation.
- Boucle jusqu'à EOF sur stdin (le parent ferme stdin pour arrêter
  proprement) ou jusqu'à ce que le process soit tué (timeout côté
  parent, voir ocr_service.py).

POURQUOI UN PROCESS PERSISTANT ET NON UN LANCEMENT PAR PAGE :
lancer un nouveau process Python à chaque page force PaddleOCR à
recharger son modèle depuis le disque à chaque fois -- sur cette
machine, ce rechargement à lui seul peut dépasser le timeout,
alors que l'OCR réel (une fois le modèle chargé) est rapide (voir
test manuel : quelques secondes). Un process persistant paie ce coût
de chargement UNE SEULE FOIS, puis traite toutes les pages suivantes
rapidement.
"""
import json
import sys


def main() -> None:
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(
            lang="fr",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except Exception as exc:
        # Échec au chargement du modèle -- inutile de continuer, le
        # parent verra ce process mourir immédiatement et le
        # redémarrera au prochain appel (voir ocr_service.py).
        print(json.dumps({"ok": False, "error": f"Chargement PaddleOCR échoué : {exc}"}), flush=True)
        sys.exit(1)

    # Signal explicite au parent : modèle chargé, prêt à recevoir des
    # chemins d'image. Le parent attend cette ligne avant d'envoyer
    # la première tâche (évite d'envoyer une image avant que le
    # modèle soit prêt).
    print(json.dumps({"ok": True, "ready": True}), flush=True)