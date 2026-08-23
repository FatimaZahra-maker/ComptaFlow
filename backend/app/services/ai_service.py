"""
app/services/ai_service.py

Service d'extraction d'informations par intelligence artificielle.
Il utilise une stratégie en CASCADE pour privilégier la vitesse et la fiabilité :

1. GROQ (Cloud, très rapide) : Extraction complète si configuré.
2. OLLAMA LOCAL (Léger) : Repli synchrone si Groq échoue. 
   On se limite à 3 champs sémantiques (nom, tiers, categorie) car un modèle 
   local est trop lourd pour une extraction exhaustive.
3. REGEX SEULE : Repli ultime si l'IA est totalement indisponible. 
   Les données sont basées sur des heuristiques.
"""
import json
import logging
import re
import requests

from app.core.config import settings
from app.services.accounting_rules_service import (
    NATURES_ECONOMIQUES_AUTORISEES,
    normaliser_nature_economique_extraite,
)
from app.services.document_classifier import detecter_type_document
from app.services.regex_extraction_service import (
    completer_champs_manquants,
    verifier_coherence_montants,
)
from app.services import groq_service
from app.services import ml_classifier_service

logger = logging.getLogger("comptaflow.ai_service")

# Paramètres de configuration pour limiter la charge locale
OLLAMA_TIMEOUT_SECONDS = 20
MAX_CHARS_PROMPT_IA = 1500
OLLAMA_KEEP_ALIVE = "30m"

# Vocabulaire strict autorisé pour la classification
_CATEGORIES_VALIDES = {
    "clients", "fournisseurs", "banque", "cnss", "tva", "impots",
    "achats", "ventes", "divers",
}

_MOTS_A_IGNORER_HEURISTIQUE = {
    "facture", "invoice", "devis", "bon de commande", "bon de livraison",
    "relevé", "avis", "déclaration",
}

# --- SCHÉMAS JSON STRICTS POUR BRIDER L'IA ---

# Schéma réduit utilisé pour l'extraction locale (Ollama)
_SCHEMA_JSON_REDUIT = """{{
  "nom_entreprise": string,
  "tiers": string,
  "nature_comptable": string | null,
  "categorie": "clients" | "fournisseurs" | "banque" | "cnss" | "tva" | "impots" | "achats" | "ventes" | "divers"
}}"""

# Schéma spécifique pour forcer l'IA à extraire des tableaux bancaires
_SCHEMA_JSON_BANQUE = """{{
  "nom_entreprise": string,
  "tiers": null,
  "categorie": "banque",
  "lignes_bancaires": [
    {{
      "date_operation": "YYYY-MM-DD",
      "libelle": string,
      "reference": string,
      "type_mouvement": "CREDIT" | "DEBIT",
      "montant": float,
      "solde_apres_operation": float
    }}
  ]
}}"""

# Dictionnaire des prompts injectés selon le type du document détecté
EXTRACTION_PROMPTS = {
    "facture": """Voici le début d'une FACTURE marocaine (texte OCR).
Identifie le nom de l'entreprise émettrice (nom_entreprise), le nom du
client/destinataire s'il est visible (tiers), et la catégorie
comptable la plus probable (categorie). Réponds UNIQUEMENT ce JSON :
Nature économique autorisée (ou null si elle n'est pas identifiable) :
""" + ", ".join(sorted(NATURES_ECONOMIQUES_AUTORISEES)) + """
Ne propose jamais de numéro de compte.
""" + _SCHEMA_JSON_REDUIT + """

Texte :
---
{texte}
---
""",
    "releve_bancaire": """Voici le début d'un RELEVÉ BANCAIRE (texte OCR).
nom_entreprise = le titulaire du compte si visible, tiers = null,
categorie = "banque". Tu dois également extraire les lignes de transactions (lignes_bancaires). Réponds UNIQUEMENT ce JSON :
""" + _SCHEMA_JSON_BANQUE + """

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
    """Extrait proprement un dictionnaire JSON depuis la réponse brute de l'IA."""
    if not texte_reponse:
        return {}
    # Nettoyage des balises Markdown (ex: ```json ... ```)
    nettoye = texte_reponse.replace("```json", "").replace("```", "").strip()
    debut, fin = nettoye.find("{"), nettoye.rfind("}")
    if debut == -1 or fin == -1 or fin < debut:
        return {}
    try:
        return json.loads(nettoye[debut : fin + 1])
    except json.JSONDecodeError:
        return {}


def _extraire_nom_entreprise_heuristique(texte_ocr: str) -> str | None:
    """Tente de deviner le nom de l'entreprise sans IA en lisant la 1ère ligne valide."""
    for ligne in texte_ocr.splitlines():
        ligne_propre = ligne.strip()
        if len(ligne_propre) < 3:
            continue
        if ligne_propre.lower() in _MOTS_A_IGNORER_HEURISTIQUE:
            continue
        # Ignore les lignes contenant uniquement des nombres/caractères spéciaux (ex: tel, ICE)
        if re.fullmatch(r"[\d\s\-/.,#]+", ligne_propre):
            continue
        return ligne_propre
    return None


def extraire_donnees_rapide(texte_ocr: str) -> dict:
    """
    Méthode de repli ultra-rapide basée UNIQUEMENT sur les expressions régulières (Regex),
    les heuristiques et le classifieur ML (si présent). Ne fait aucun appel réseau.
    """
    type_document = detecter_type_document(texte_ocr)

    # Squelette de base des données
    donnees: dict = {
        "nom_entreprise": None,
        "ice": None,
        "identifiant_fiscal": None,
        "rc": None,
        "type_document": type_document,
        "categorie": "divers",
        "date_piece": None,
        "numero_piece": None,
        "nature_comptable": None,
        "tiers": None,
        "montant_ht": None,
        "taux_tva": None,
        "montant_tva": None,
        "montant_ttc": None,
        "confiance_par_champ": {},
        "enrichissement_ia_statut": "en_attente",
    }

    # Remplissage via regex
    donnees = completer_champs_manquants(donnees, texte_ocr)
    conf = donnees["confiance_par_champ"]

    # Remplissage sémantique basique sans IA
    fallback = _extraire_nom_entreprise_heuristique(texte_ocr)
    donnees["nom_entreprise"] = fallback
    conf["nom_entreprise"] = 0.35 if fallback else 0.0
    conf["tiers"] = 0.0

    # Classification via un modèle ML classique (non-LLM)
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
    Appelle Ollama en local. Demande volontairement très peu de choses (3 champs) 
    pour éviter de surcharger un modèle 1B ou 8B sur une petite machine.
    """
    # Troncature pour limiter le contexte et accélérer l'inférence
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

    # Validation et ajout d'un score de confiance artificiel (selon si le mot existe dans le texte)
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

    nature = normaliser_nature_economique_extraite(
        champs_ia.get("nature_comptable")
    )
    if nature is not None and type_document == "facture":
        resultat["nature_comptable"] = nature

    return resultat


def _extraire_donnees_locale_synchrone(texte_ocr: str) -> dict:
    """
    Processus de repli complet : On effectue d'abord une passe rapide (Regex),
    puis on tente d'enrichir les champs difficiles (nom, catégorie) avec l'IA locale.
    """
    donnees = extraire_donnees_rapide(texte_ocr)
    type_document = donnees.get("type_document", "autre")

    resultat_ia = enrichir_avec_ia(texte_ocr, type_document)
    if not resultat_ia:
        donnees["enrichissement_ia_statut"] = "echec"
        return donnees

    conf = donnees["confiance_par_champ"]

    # Écrasement des champs devinés par la regex avec ceux de l'IA (meilleurs)
    if "nom_entreprise" in resultat_ia:
        donnees["nom_entreprise"] = resultat_ia["nom_entreprise"]
        conf["nom_entreprise"] = resultat_ia["conf_nom_entreprise"]

    if "tiers" in resultat_ia:
        donnees["tiers"] = resultat_ia["tiers"]
        conf["tiers"] = resultat_ia["conf_tiers"]

    if "categorie" in resultat_ia:
        donnees["categorie"] = resultat_ia["categorie"]
        conf["categorie"] = resultat_ia["conf_categorie"]

    if "nature_comptable" in resultat_ia:
        donnees["nature_comptable"] = resultat_ia["nature_comptable"]
        conf["nature_comptable"] = 0.75

    donnees["enrichissement_ia_statut"] = "termine"
    return donnees


def prechauffer_modele() -> None:
    """
    Préchauffe Ollama en mémoire au démarrage.
    Sécurité vitale : Annulé si la machine a moins de 1.8 Go de RAM libre.
    """
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
    Définit l'ordre strict de la cascade de secours.
    """
    # 1. Tentative avec l'API Cloud Rapide (Groq)
    if settings.GROQ_API_KEY:
        donnees_groq = groq_service.extraire_et_classifier(texte_ocr)
        if donnees_groq is not None:
            return donnees_groq
        logger.warning("Groq indisponible/échoué -- repli DIRECT sur Ollama local.")

    # 2. Tentative Local Synchrone (Regex + Ollama partiel)
    return _extraire_donnees_locale_synchrone(texte_ocr)
