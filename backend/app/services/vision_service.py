"""
app/services/vision_service.py

Extraction ET classification directement depuis l'IMAGE d'une page,
via le modèle vision de Groq (qwen/qwen3.6-27b).

Ce script intègre :
- Le retry intelligent pour les erreurs réseau transitoires.
- Des règles de prompt strictes pour gérer les cas réels (tampons SAISIE/PC, 
  mots clés comme "Total net", dates multiples).
- Un post-traitement mathématique pour sécuriser l'équation HT + TVA = TTC.
"""
import base64
import json
import logging
import time

import requests

from app.core.config import settings
from app.services.gemini_service import _construire_donnees

logger = logging.getLogger("comptaflow.vision_service")

_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODELE_VISION = "qwen/qwen3.6-27b"

_TIMEOUT_SECONDS = 45 
_NOMBRE_TENTATIVES = 2
_DELAI_ENTRE_TENTATIVES_SEC = 1.5

_SCHEMA_JSON = """{
  "nom_fournisseur": string | null,
  "ice_fournisseur": string | null,
  "if_fournisseur": string | null,
  "rc_fournisseur": string | null,
  "nom_client": string | null,
  "ice_client": string | null,
  "if_client": string | null,
  "rc_client": string | null,
  "categorie_document": "facture" | "releve_bancaire" | "avis_cnss" | "avis_tva" | "autre",
  "date_piece": string | null,
  "numero_piece": string | null,
  "montant_ht": number | null,
  "taux_tva": number | null,
  "montant_tva": number | null,
  "montant_ttc": number | null
}"""

_PROMPT_TEXTE = """Tu es un assistant comptable marocain expert. Voici l'IMAGE
d'un document comptable scanné par un cabinet comptable. Lis-la attentivement,
même si la qualité est moyenne (photo, scan incliné, léger flou, tampons), et extrait
TOUS les champs demandés, avec la plus grande précision.

IMPORTANT -- une facture a DEUX parties distinctes, ne les confonds jamais :
- Le FOURNISSEUR/ÉMETTEUR : celui qui a créé et envoyé la facture (généralement en haut, dans l'entête)
- Le CLIENT/DESTINATAIRE : celui à qui la facture est adressée (généralement après "À :", "Client :", "Adressé à :")
Extrait séparément le nom/ICE/IF/RC de CHACUNE de ces deux parties.

categorie_document (type physique du document, PAS la direction comptable) :
- "facture" : facture standard (achat ou vente, peu importe)
- "releve_bancaire" : relevé bancaire, avis de virement, RIB
- "avis_cnss" : avis ou bordereau CNSS
- "avis_tva" : déclaration ou avis de TVA
- "autre" : tout le reste

RÈGLES D'EXTRACTION STRICTES :
1. NUMÉRO DE PIÈCE : Cherche explicitement "Facture n°", "N°", ou "Invoice". Ignore totalement les numéros de devis (ex: "Devis n°") ou de bons de commande.
2. DATES : S'il y a plusieurs dates, extrais UNIQUEMENT la date d'émission du document (ex: "Casablanca le..."). Ignore les dates de devis, de livraison, ou les dates manuscrites de paiement. Format obligatoire : YYYY-MM-DD.
3. MONTANTS (HT / TVA / TTC) : nombres décimaux (ex: 1234.50), jamais de texte, jamais de symbole monétaire.
   - Attention au vocabulaire : "Total net", "Total" ou "Sous-total" désignent souvent le montant HT si une ligne TVA suit.
   - Si le document est une facture d'eau/électricité (ex: Lydec, REDAL, RADEEMA) et que seule la somme à payer est visible, place ce montant dans 'montant_ttc' et laisse HT et TVA à 'null'.
   - Si taux_tva = 0 (ou "TVA 0%"), alors montant_ht DOIT être égal à montant_ttc.
4. RELEVÉS BANCAIRES : Si categorie_document est "releve_bancaire", les champs montant_ht, taux_tva, montant_tva et montant_ttc DOIVENT TOUJOURS être "null". Ne tente jamais de calculer un total sur un relevé.
5. PARASITES VISUELS : Ignore totalement les tampons comptables (ex: "SAISIE / PC") et les écritures manuscrites au stylo (ex: ratures, "payé le", "vir le", codes comptables gribouillés). Base-toi uniquement sur le texte imprimé d'origine.
6. IDENTIFIANTS MAROCAINS : ICE = 15 chiffres, IF = 6 à 8 chiffres, RC = 1 à 8 chiffres, CNSS = 7 à 9 chiffres. Ne JAMAIS inventer une valeur.

Réponds UNIQUEMENT avec un objet JSON valide suivant EXACTEMENT ce schéma,
sans aucun texte avant ou après, sans balises markdown :
""" + _SCHEMA_JSON


def _encoder_image_base64(chemin_image: str) -> str:
    with open(chemin_image, "rb") as fichier:
        return base64.b64encode(fichier.read()).decode("utf-8")


def _nettoyer_et_parser_json(texte_reponse: str) -> dict | None:
    if not texte_reponse:
        return None
    nettoye = texte_reponse.replace("```json", "").replace("```", "").strip()
    debut, fin = nettoye.find("{"), nettoye.rfind("}")
    if debut == -1 or fin == -1 or fin < debut:
        return None
    try:
        return json.loads(nettoye[debut : fin + 1])
    except json.JSONDecodeError:
        return None


def _erreur_est_transitoire(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def _appeler_groq_vision_avec_retry(image_b64: str) -> str | None:
    corps = {
        "model": _MODELE_VISION,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT_TEXTE},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_completion_tokens": 2048, 
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for tentative in range(1, _NOMBRE_TENTATIVES + 1):
        try:
            reponse = requests.post(_URL, headers=headers, json=corps, timeout=_TIMEOUT_SECONDS)
            reponse.raise_for_status()
            contenu = reponse.json()
            return contenu["choices"][0]["message"]["content"]
        except (requests.exceptions.RequestException, KeyError, IndexError) as exc:
            corps_reponse = ""
            if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
                corps_reponse = f" | Réponse serveur : {exc.response.text[:500]}"

            if _erreur_est_transitoire(exc) and tentative < _NOMBRE_TENTATIVES:
                logger.warning(
                    "Appel Groq vision échoué (tentative %s/%s, transitoire), retry dans %ss : %s%s",
                    tentative, _NOMBRE_TENTATIVES, _DELAI_ENTRE_TENTATIVES_SEC, exc, corps_reponse,
                )
                time.sleep(_DELAI_ENTRE_TENTATIVES_SEC)
                continue

            logger.warning(
                "Appel Groq vision définitivement échoué (tentative %s/%s) : %s%s",
                tentative, _NOMBRE_TENTATIVES, exc, corps_reponse,
            )
            return None

    return None


def _valider_et_corriger_montants(donnees: dict) -> dict:
    """
    Vérifie et corrige la cohérence mathématique des montants (HT, TVA, TTC).
    """
    if not donnees:
        return donnees

    if donnees.get("categorie_document") == "releve_bancaire":
        donnees["montant_ht"] = None
        donnees["montant_tva"] = None
        donnees["montant_ttc"] = None
        donnees["taux_tva"] = None
        return donnees

    def vers_float(valeur):
        if valeur is None:
            return None
        try:
            return float(valeur)
        except (ValueError, TypeError):
            return None

    ht = vers_float(donnees.get("montant_ht"))
    tva = vers_float(donnees.get("montant_tva"))
    ttc = vers_float(donnees.get("montant_ttc"))
    taux = vers_float(donnees.get("taux_tva"))

    # Déductions logiques des montants manquants
    if ht is not None and tva is not None and ttc is None:
        ttc = round(ht + tva, 2)
    elif ht is not None and ttc is not None and tva is None:
        tva = round(ttc - ht, 2)
    elif ttc is not None and taux is not None and ht is None:
        ht = round(ttc / (1 + (taux / 100)), 2)
        tva = round(ttc - ht, 2)
    elif ht is not None and taux is not None and tva is None:
        tva = round(ht * (taux / 100), 2)
        ttc = round(ht + tva, 2)

    # Correction des erreurs d'arrondi ou d'hallucination (tolérance 0.5)
    if ht is not None and tva is not None and ttc is not None:
        if abs((ht + tva) - ttc) > 0.5:
            tva = round(ttc - ht, 2)

    donnees["montant_ht"] = ht
    donnees["montant_tva"] = tva
    donnees["montant_ttc"] = ttc
    if taux is not None:
         donnees["taux_tva"] = taux

    return donnees


def extraire_et_classifier_depuis_image(chemin_image: str) -> dict | None:
    if not settings.GROQ_API_KEY:
        return None

    try:
        image_b64 = _encoder_image_base64(chemin_image)
    except OSError as exc:
        logger.warning("Lecture image impossible pour la vision Groq : %s", exc)
        return None

    texte_json = _appeler_groq_vision_avec_retry(image_b64)
    if texte_json is None:
        return None

    champs = _nettoyer_et_parser_json(texte_json)
    if champs is None:
        logger.warning("Réponse Groq vision non-JSON exploitable -- page ignorée.")
        return None

    donnees = _construire_donnees(champs)
    donnees["source_extraction"] = "groq_vision"
    
    # Validation mathématique avant retour
    donnees = _valider_et_corriger_montants(donnees)
    
    return donnees