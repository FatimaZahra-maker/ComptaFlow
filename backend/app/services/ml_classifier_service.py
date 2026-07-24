"""
app/services/ml_classifier_service.py

Charge le classifieur ML (scikit-learn) entraîné par
scripts/train_categorie_classifier.py, et prédit la catégorie d'un
document à partir de son texte OCR -- en quelques millisecondes,
sans appel réseau, sans dépendance à la RAM disponible pour un LLM.

Si le modèle n'a pas encore été entraîné (fichier .joblib absent),
predire_categorie() retourne None -- le pipeline retombe alors sur la
valeur par défaut "divers" (ou sur l'enrichissement IA existant si tu
le gardes en parallèle), sans jamais lever d'exception bloquante.
"""
import logging
from pathlib import Path

logger = logging.getLogger("comptaflow.ml_classifier")

_CHEMIN_MODELE = Path(__file__).resolve().parent.parent / "ml_models" / "categorie_classifier.joblib"

_modele = None
_modele_charge = False


def _charger_modele():
    global _modele, _modele_charge
    if _modele_charge:
        return _modele
    _modele_charge = True
    if not _CHEMIN_MODELE.exists():
        logger.warning(
            "Modèle ML de classification introuvable (%s) -- lance "
            "scripts/train_categorie_classifier.py pour l'entraîner.",
            _CHEMIN_MODELE,
        )
        return None
    try:
        import joblib
        _modele = joblib.load(_CHEMIN_MODELE)
        logger.info("Modèle ML de classification chargé (%s).", _CHEMIN_MODELE)
    except Exception as exc:
        logger.error("Échec du chargement du modèle ML : %s", exc)
        _modele = None
    return _modele


def predire_categorie(texte_ocr: str) -> tuple[str | None, float]:
    """
    Retourne (categorie_predite, confiance) ou (None, 0.0) si le modèle
    n'est pas disponible ou si la prédiction échoue. Ne lève jamais
    d'exception -- doit rester silencieusement dégradable.
    """
    modele = _charger_modele()
    if modele is None or not texte_ocr or not texte_ocr.strip():
        return None, 0.0

    try:
        categorie = modele.predict([texte_ocr])[0]
        probabilites = modele.predict_proba([texte_ocr])[0]
        confiance = float(max(probabilites))
        return categorie, confiance
    except Exception as exc:
        logger.warning("Échec de la prédiction ML : %s", exc)
        return None, 0.0