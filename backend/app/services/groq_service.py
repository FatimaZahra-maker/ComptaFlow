"""
app/services/groq_service.py

Extraction ET classification COMPLÈTES d'un document comptable en UN
SEUL appel à l'API Groq (inférence LLM cloud très rapide, modèles
Llama), avec le même contrat de sortie que gemini_service.py --
réutilise sa fonction de mise en forme _construire_donnees pour ne
jamais désynchroniser les deux formats.

Groq est le FOURNISSEUR CLOUD PRIORITAIRE du pipeline (voir
ai_service.extraire_donnees) : si GROQ_API_KEY est configurée, chaque
document passe d'abord par Groq. En cas d'échec (réseau, quota, clé
invalide, timeout, JSON invalide), la fonction retourne None -- c'est
ai_service.extraire_donnees() qui bascule alors DIRECTEMENT sur Ollama
en local, de façon synchrone dans le chemin critique, jamais
d'exception qui ferait échouer le document.

Contrairement à Gemini, l'API Groq (compatible OpenAI) ne supporte pas
de schéma JSON strict imposé par le serveur -- "response_format:
json_object" garantit un JSON valide, mais pas sa structure exacte. Le
schéma attendu est donc décrit explicitement dans le prompt.
"""
import json
import logging

import requests

from app.core.config import settings
from app.services.gemini_service import _construire_donnees

logger = logging.getLogger("comptaflow.groq_service")

_URL = "https://api.groq.com/openai/v1/chat/completions"

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

_PROMPT = """Tu es un assistant comptable marocain expert. Voici le texte OCR
brut d'un document comptable scanné par un cabinet comptable. Analyse-le et
extrait TOUS les champs demandés, avec la plus grande précision.

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

RÈGLES D'EXTRACTION :
- numero_piece : UNIQUEMENT le numéro de référence explicite du document (ex: après "Facture n°", "Facture #", "N°", "Invoice"). NE JAMAIS utiliser un nom de personne, d'entreprise ou de cabinet comme numéro de pièce.
- montant_ht / montant_tva / montant_ttc : nombres décimaux (ex: 1234.50), jamais de texte, jamais de symbole monétaire.
- Si le document affiche "Sous-total" (ou équivalent), traite-le comme montant_ht.
- Si taux_tva = 0 (ou "TVA 0%"), alors montant_ht DOIT être égal à montant_ttc (déduis-le si besoin).
- Si un seul montant total (TTC) est visible avec un taux de TVA non nul, tu PEUX déduire HT et TVA par le calcul (HT = TTC / (1 + taux/100)).
- date_piece : uniquement au format YYYY-MM-DD. Si ambiguë ou absente, laisse null.
- Ne JAMAIS inventer une valeur : si un champ n'est pas identifiable dans le texte, renvoie null.
- ICE = 15 chiffres, IF = 6-8 chiffres, RC = 3-8 chiffres -- uniquement des identifiants marocains standards, jamais un numéro de téléphone ou de compte bancaire.

Réponds UNIQUEMENT avec un objet JSON valide suivant EXACTEMENT ce schéma,
sans aucun texte avant ou après, sans balises markdown :
""" + _SCHEMA_JSON + """

Texte OCR à analyser :
---
{texte}
---
"""

_MAX_CHARS_PROMPT = 4000


def _nettoyer_et_parser_json(texte_reponse: str) -> dict | None:
    """Groq en mode json_object renvoie normalement du JSON pur, mais
    on nettoie quand même par sécurité (le modèle peut parfois ajouter
    des balises ```json autour malgré la consigne)."""
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


def extraire_et_classifier(texte_ocr: str) -> dict | None:
    """
    Point d'entrée principal, appelé par ai_service.extraire_donnees()
    EN PREMIER si settings.GROQ_API_KEY est configurée. Retourne None
    en cas d'échec quelconque -- jamais d'exception, pour permettre un
    repli propre et immédiat sur Ollama.
    """
    if not settings.GROQ_API_KEY:
        return None
    if not texte_ocr or not texte_ocr.strip():
        return None

    texte_court = texte_ocr[:_MAX_CHARS_PROMPT]

    corps = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "user", "content": _PROMPT.format(texte=texte_court)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 512,
    }
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        reponse = requests.post(
            _URL, headers=headers, json=corps, timeout=settings.GROQ_TIMEOUT_SECONDS,
        )
        reponse.raise_for_status()
        contenu = reponse.json()
        texte_json = contenu["choices"][0]["message"]["content"]
    except (requests.exceptions.RequestException, KeyError, IndexError) as exc:
        logger.warning("Appel Groq échoué (repli direct sur Ollama) : %s", exc)
        return None

    champs = _nettoyer_et_parser_json(texte_json)
    if champs is None:
        logger.warning("Réponse Groq non-JSON exploitable -- repli direct sur Ollama.")
        return None

    return _construire_donnees(champs)