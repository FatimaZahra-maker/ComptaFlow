"""
app/services/gemini_service.py

Extraction ET classification COMPLÈTES d'un document comptable en UN
SEUL appel à l'API Gemini, avec sortie JSON structurée (responseSchema) 
-- pas de parsing fragile de texte libre.

Remplace, quand settings.AI_PROVIDER == "cloud", les DEUX phases de
ai_service.py (regex rapide + enrichissement IA différé) par UNE SEULE
passe cloud, appelée directement dans le chemin critique du pipeline
(document_processing.py) : objectif quelques secondes par facture.

Dégradation gracieuse : si l'appel Gemini échoue (réseau, quota, clé
invalide, timeout) ou renvoie un JSON invalide, la fonction retourne
None -- c'est ai_service.extraire_donnees() qui retombe alors sur
extraire_donnees_rapide() (regex locale), jamais d'exception qui
ferait échouer tout le document.
"""
import json
import logging

import requests

from app.core.config import settings
from app.services.regex_extraction_service import verifier_coherence_montants

logger = logging.getLogger("comptaflow.gemini_service")

_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"
)

_CATEGORIES_VALIDES = [
    "clients", "fournisseurs", "banque", "cnss", "tva", "impots", "achats", "ventes", "divers",
]

_MAX_CHARS_PROMPT = 4000  # largement suffisant pour une facture/relevé -- garde le call rapide

_SCHEMA_REPONSE = {
    "type": "OBJECT",
    "properties": {
        "nom_fournisseur": {"type": "STRING", "nullable": True},
        "ice_fournisseur": {"type": "STRING", "nullable": True},
        "if_fournisseur": {"type": "STRING", "nullable": True},
        "rc_fournisseur": {"type": "STRING", "nullable": True},
        "nom_client": {"type": "STRING", "nullable": True},
        "ice_client": {"type": "STRING", "nullable": True},
        "if_client": {"type": "STRING", "nullable": True},
        "rc_client": {"type": "STRING", "nullable": True},
        "categorie_document": {
            "type": "STRING",
            "enum": ["facture", "releve_bancaire", "avis_cnss", "avis_tva", "autre"],
        },
        "date_piece": {"type": "STRING", "nullable": True, "description": "Format YYYY-MM-DD"},
        "numero_piece": {"type": "STRING", "nullable": True},
        "montant_ht": {"type": "NUMBER", "nullable": True},
        "taux_tva": {"type": "NUMBER", "nullable": True},
        "montant_tva": {"type": "NUMBER", "nullable": True},
        "montant_ttc": {"type": "NUMBER", "nullable": True},
    },
    "required": ["categorie_document"],
}

_PROMPT = """Tu es un assistant comptable marocain expert. Voici le texte OCR
brut d'un document comptable scanné par un cabinet comptable. Analyse-le et
extrait TOUS les champs demandés, avec la plus grande précision.

IMPORTANT -- une facture a DEUX parties distinctes, ne les confonds jamais :
- Le FOURNISSEUR/ÉMETTEUR : celui qui a créé et envoyé la facture (généralement en haut, dans l'entête)
- Le CLIENT/DESTINATAIRE : celui à qui la facture est adressée (généralement après "À :", "Client :", "Adressé à :")
Extrait séparément le nom/ICE/IF/RC de CHACUNE de ces deux parties.

categorie_document (type physique du document, PAS la direction comptable) :
- "facture" : facture standard (achat ou vente, peu importe -- la direction sera déterminée ailleurs)
- "releve_bancaire" : relevé bancaire, avis de virement, RIB
- "avis_cnss" : avis ou bordereau CNSS
- "avis_tva" : déclaration ou avis de TVA
- "autre" : tout le reste

RÈGLES D'EXTRACTION :
- numero_piece : UNIQUEMENT le numéro de référence explicite du document (ex: après "Facture n°", "Facture #", "N°", "Invoice"). NE JAMAIS utiliser un nom de personne, d'entreprise ou de cabinet comme numéro de pièce.
- montant_ht / montant_tva / montant_ttc : nombres décimaux (ex: 1234.50), jamais de texte, jamais de symbole monétaire.
- Si le document affiche "Sous-total" (ou équivalent), traite-le comme montant_ht.
- Si taux_tva = 0 (ou "TVA 0%"), alors montant_ht DOIT être égal à montant_ttc (déduis-le si besoin).
- Si un seul montant total (TTC) est visible avec un taux de TVA non nul, tu PEUX déduire HT et TVA par le calcul (HT = TTC / (1 + taux/100)).
- date_piece : uniquement au format YYYY-MM-DD. Si ambiguë ou absente, laisse null.
- Ne JAMAIS inventer une valeur : si un champ n'est pas identifiable dans le texte, renvoie null.
- ICE = 15 chiffres, IF = 6-8 chiffres, RC = 3-8 chiffres -- uniquement des identifiants marocains standards, jamais un numéro de téléphone ou de compte bancaire.

Texte OCR à analyser :
---
{texte}
---
"""


def extraire_et_classifier(texte_ocr: str) -> dict | None:
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY absente -- appel Gemini sauté.")
        return None
    if not texte_ocr or not texte_ocr.strip():
        return None

    texte_court = texte_ocr[:_MAX_CHARS_PROMPT]
    url = _URL_TEMPLATE.format(modele=settings.GEMINI_MODEL)

    corps = {
        "contents": [{"parts": [{"text": _PROMPT.format(texte=texte_court)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _SCHEMA_REPONSE,
            "temperature": 0.1,
            "maxOutputTokens": 512,
        },
    }

    try:
        reponse = requests.post(
            url, params={"key": settings.GEMINI_API_KEY}, json=corps,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )
        reponse.raise_for_status()
        contenu = reponse.json()
        texte_json = contenu["candidates"][0]["content"]["parts"][0]["text"]
    except (requests.exceptions.RequestException, KeyError, IndexError) as exc:
        logger.warning("Appel Gemini échoué (repli local prévu) : %s", exc)
        return None

    try:
        champs = json.loads(texte_json)
    except json.JSONDecodeError:
        logger.warning("Réponse Gemini non-JSON malgré responseSchema -- repli local.")
        return None

    return _construire_donnees(champs)


def _construire_donnees(champs: dict) -> dict:
    """Remet les champs Gemini au format pipeline. Ne fixe PAS encore
    'categorie' comptable (achats/ventes) -- ça se décide dans
    company_service.py en comparant fournisseur/client aux entreprises
    connues du cabinet. On propage ici le type physique + les DEUX
    parties, et la déduction HT si taux_tva=0."""
    ht = champs.get("montant_ht")
    tva = champs.get("montant_tva")
    ttc = champs.get("montant_ttc")
    taux = champs.get("taux_tva")

    if ht is None and ttc is not None and (taux == 0 or (tva == 0 and taux is None)):
        ht = ttc
        if tva is None:
            tva = 0

    donnees = {
        "nom_fournisseur": champs.get("nom_fournisseur"),
        "ice_fournisseur": champs.get("ice_fournisseur"),
        "if_fournisseur": champs.get("if_fournisseur"),
        "rc_fournisseur": champs.get("rc_fournisseur"),
        "nom_client": champs.get("nom_client"),
        "ice_client": champs.get("ice_client"),
        "if_client": champs.get("if_client"),
        "rc_client": champs.get("rc_client"),
        # Compat rétro : le reste du pipeline (company_service, avant
        # correction) lisait "nom_entreprise"/"ice"/"identifiant_fiscal"/"rc"
        # -- on les garde alignés sur le FOURNISSEUR par défaut ; c'est
        # identifier_ou_creer_entreprise_avec_direction() qui tranchera.
        "nom_entreprise": champs.get("nom_fournisseur"),
        "ice": champs.get("ice_fournisseur"),
        "identifiant_fiscal": champs.get("if_fournisseur"),
        "rc": champs.get("rc_fournisseur"),
        "type_document": champs.get("categorie_document") or "autre",
        "categorie": "divers",  # sera écrasé par company_service selon la direction détectée
        "date_piece": champs.get("date_piece"),
        "numero_piece": champs.get("numero_piece"),
        "tiers": champs.get("nom_client") or champs.get("nom_fournisseur"),
        "montant_ht": ht,
        "taux_tva": taux,
        "montant_tva": tva,
        "montant_ttc": ttc,
        "confiance_par_champ": {
            cle: (0.90 if champs.get(cle) is not None else 0.0)
            for cle in (
                "nom_fournisseur", "ice_fournisseur", "nom_client", "ice_client",
                "date_piece", "numero_piece", "montant_ht", "taux_tva", "montant_tva", "montant_ttc",
            )
        },
        "enrichissement_ia_statut": "termine",
    }

    donnees = verifier_coherence_montants(donnees)
    return donnees