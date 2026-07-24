"""
app/services/ai_service.py

Extraction en CASCADE, priorité vitesse + fiabilité :

1. GROQ (cloud, rapide) -- si GROQ_API_KEY configurée. Extraction ET
   classification complètes en un seul appel, DANS le chemin critique.

2. OLLAMA LOCAL (léger) -- repli DIRECT et SYNCHRONE si Groq n'est pas
   configuré ou échoue. Utilise regex (fiable à ~100% sur les champs
   numériques/identifiants) + UN appel Ollama limité à 3 champs
   sémantiques (nom_entreprise, tiers, categorie) -- pas une extraction
   complète à 15 champs, qui serait trop lourde pour un modèle 1B sur
   une machine à RAM limitée (cause historique des timeouts/lenteurs
   de ce projet).

3. REGEX SEULE -- si Ollama est lui aussi injoignable, les champs déjà
   trouvés par regex/heuristique restent tels quels.

Cette fonction est TOUJOURS garantie de retourner un dict exploitable.
"""
import json
import logging
import re

import requests

from app.core.config import settings
from app.services.document_classifier import detecter_type_document
from app.services.regex_extraction_service import (
    completer_champs_manquants,
    verifier_coherence_montants,
)
from app.services import groq_service
from app.services import ml_classifier_service

logger = logging.getLogger("comptaflow.ai_service")

OLLAMA_TIMEOUT_SECONDS = 20
MAX_CHARS_PROMPT_IA = 1500
OLLAMA_KEEP_ALIVE = "30m"

_CATEGORIES_VALIDES = {
    "clients", "fournisseurs", "banque", "cnss", "tva", "impots",
    "achats", "ventes", "divers",
}

_MOTS_A_IGNORER_HEURISTIQUE = {
    "facture", "invoice", "devis", "bon de commande", "bon de livraison",
    "relevé", "avis", "déclaration",
}

_SCHEMA_JSON_REDUIT = """{{
  "nom_entreprise": string,
  "tiers": string,
  "categorie": "clients" | "fournisseurs" | "banque" | "cnss" | "tva" | "impots" | "achats" | "ventes" | "divers"
}}"""

EXTRACTION_PROMPTS = {
    "facture": """Voici le début d'une FACTURE marocaine (texte OCR).
Identifie le nom de l'entreprise émettrice (nom_entreprise), le nom du
client/destinataire s'il est visible (tiers), et la catégorie
comptable la plus probable (categorie). Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
    "releve_bancaire": """Voici le début d'un RELEVÉ BANCAIRE (texte OCR).
nom_entreprise = le titulaire du compte si visible, tiers = null,
categorie = "banque". Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
    "avis_cnss": """Voici le début d'un AVIS CNSS (texte OCR).
nom_entreprise = l'entreprise affiliée, tiers = "CNSS",
categorie = "cnss". Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
    "avis_tva": """Voici le début d'un AVIS/DÉCLARATION TVA (texte OCR).
categorie = "tva". Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
    "autre": """Voici le début d'un document comptable (texte OCR).
Identifie nom_entreprise, tiers, et categorie la plus probable.
Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
}


def _nettoyer_et_parser_json(texte_reponse: str) -> dict:
    if not texte_reponse:
        return {}
    nettoye = texte_reponse.replace("```json", "").replace("```", "").strip()
    debut, fin = nettoye.find("{"), nettoye.rfind("}")
    if debut == -1 or fin == -1 or fin < debut:
        return {}
    try:
        return json.loads(nettoye[debut : fin + 1])
    except json.JSONDecodeError:
        return {}


def _extraire_nom_entreprise_heuristique(texte_ocr: str) -> str | None:
    for ligne in texte_ocr.splitlines():
        ligne_propre = ligne.strip()
        if len(ligne_propre) < 3:
            continue
        if ligne_propre.lower() in _MOTS_A_IGNORER_HEURISTIQUE:
            continue
        if re.fullmatch(r"[\d\s\-/.,#]+", ligne_propre):
            continue
        return ligne_propre
    return None


def extraire_donnees_rapide(texte_ocr: str) -> dict:
    """
    Base regex + heuristique + ML (categorie, si modèle entraîné).
    Aucun appel réseau. Ne lève jamais d'exception.
    """
    type_document = detecter_type_document(texte_ocr)

    donnees: dict = {
        "nom_entreprise": None,
        "ice": None,
        "identifiant_fiscal": None,
        "rc": None,
        "type_document": type_document,
        "categorie": "divers",
        "date_piece": None,
        "numero_piece": None,
        "tiers": None,
        "montant_ht": None,
        "taux_tva": None,
        "montant_tva": None,
        "montant_ttc": None,
        "confiance_par_champ": {},
        "enrichissement_ia_statut": "en_attente",
    }

    donnees = completer_champs_manquants(donnees, texte_ocr)
    conf = donnees["confiance_par_champ"]

    fallback = _extraire_nom_entreprise_heuristique(texte_ocr)
    donnees["nom_entreprise"] = fallback
    conf["nom_entreprise"] = 0.35 if fallback else 0.0
    conf["tiers"] = 0.0

    categorie_ml, confiance_ml = ml_classifier_service.predire_categorie(texte_ocr)
    if categorie_ml:
        donnees["categorie"] = categorie_ml
        conf["categorie"] = confiance_ml
    else:
        conf["categorie"] = 0.30

    donnees = verifier_coherence_montants(donnees)

    return donnees


def enrichir_avec_ia(texte_ocr: str, type_document: str) -> dict:
    """
    Appel Ollama LÉGER : uniquement les 3 champs sémantiques que la
    regex ne peut pas deviner. Utilisée en repli synchrone quand Groq
    est indisponible -- jamais d'extraction complète via ce petit
    modèle local, trop lourde/peu fiable pour cette tâche.
    """
    texte_court = texte_ocr[:MAX_CHARS_PROMPT_IA]
    prompt = EXTRACTION_PROMPTS[type_document].format(texte=texte_court)
    texte_lower = texte_ocr.lower()

    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 150, "num_ctx": 2048},
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        champs_ia = _nettoyer_et_parser_json(response.json().get("response", ""))
    except (requests.exceptions.RequestException, KeyError) as exc:
        logger.warning("Appel Ollama échoué : %s", exc)
        return {}

    if not champs_ia:
        logger.warning("Ollama : réponse reçue mais JSON vide/invalide après nettoyage.")

    resultat: dict = {}

    if champs_ia.get("nom_entreprise"):
        val = str(champs_ia["nom_entreprise"]).strip()
        resultat["nom_entreprise"] = val
        resultat["conf_nom_entreprise"] = 0.85 if val.lower() in texte_lower else 0.40

    if champs_ia.get("tiers"):
        val = str(champs_ia["tiers"]).strip()
        resultat["tiers"] = val
        resultat["conf_tiers"] = 0.85 if val.lower() in texte_lower else 0.40

    categorie_ia = str(champs_ia.get("categorie") or "").strip().lower()
    if categorie_ia in _CATEGORIES_VALIDES:
        resultat["categorie"] = categorie_ia
        resultat["conf_categorie"] = 0.90 if categorie_ia != "divers" else 0.50
    elif categorie_ia:
        logger.warning("Ollama : categorie '%s' hors vocabulaire valide, ignorée.", categorie_ia)

    return resultat


def _extraire_donnees_locale_synchrone(texte_ocr: str) -> dict:
    """
    Repli LOCAL DIRECT (synchrone) : regex (rapide, fiable) fusionnée
    avec un appel Ollama BLOQUANT léger pour 3 champs sémantiques
    seulement. Si Ollama échoue aussi, le résultat regex/heuristique
    est retourné tel quel -- jamais d'exception.
    """
    donnees = extraire_donnees_rapide(texte_ocr)
    type_document = donnees.get("type_document", "autre")

    resultat_ia = enrichir_avec_ia(texte_ocr, type_document)
    if not resultat_ia:
        donnees["enrichissement_ia_statut"] = "echec"
        return donnees

    conf = donnees["confiance_par_champ"]

    if "nom_entreprise" in resultat_ia:
        donnees["nom_entreprise"] = resultat_ia["nom_entreprise"]
        conf["nom_entreprise"] = resultat_ia["conf_nom_entreprise"]

    if "tiers" in resultat_ia:
        donnees["tiers"] = resultat_ia["tiers"]
        conf["tiers"] = resultat_ia["conf_tiers"]

    if "categorie" in resultat_ia:
        donnees["categorie"] = resultat_ia["categorie"]
        conf["categorie"] = resultat_ia["conf_categorie"]

    donnees["enrichissement_ia_statut"] = "termine"
    return donnees


def prechauffer_modele() -> None:
    """Préchauffage Ollama -- SAUTÉ si la RAM disponible est trop basse."""
    try:
        import psutil
        ram_disponible_mb = psutil.virtual_memory().available / (1024 * 1024)
        if ram_disponible_mb < 1800:
            logger.warning(
                "RAM disponible trop faible (%.0f MB) -- préchauffage Ollama SAUTÉ.",
                ram_disponible_mb,
            )
            return
    except ImportError:
        pass

    try:
        logger.info("Préchauffage du modèle Ollama (%s)...", settings.OLLAMA_MODEL)
        requests.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": "Bonjour",
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 5},
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        logger.info("Modèle Ollama préchauffé.")
    except requests.exceptions.RequestException as exc:
        logger.warning("Préchauffage Ollama échoué (non bloquant) : %s", exc)


def extraire_donnees(texte_ocr: str) -> dict:
    """
    Point d'entrée UNIQUE utilisé par document_processing.py.

    Cascade EXACTE demandée : Groq -> Ollama local (léger) -> regex seule.
    """
    if settings.GROQ_API_KEY:
        donnees_groq = groq_service.extraire_et_classifier(texte_ocr)
        if donnees_groq is not None:
            return donnees_groq
        logger.warning("Groq indisponible/échoué -- repli DIRECT sur Ollama local.")

    return _extraire_donnees_locale_synchrone(texte_ocr)