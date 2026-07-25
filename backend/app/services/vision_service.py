"""
app/services/vision_service.py

Extraction ET classification directement depuis l'IMAGE d'une page,
via le modèle vision de Groq (qwen/qwen3.6-27b).

CORRECTIF (retry intelligent) : la version précédente retentait sur
TOUTE exception, y compris les erreurs 4xx (ex: 400 Bad Request) qui
ne se corrigent jamais en réessayant à l'identique -- gaspillant du
temps (30s+ perdues) avant d'abandonner. Le retry ne s'applique
désormais qu'aux erreurs réellement transitoires : timeout, coupure de
connexion, ou erreur serveur (5xx). Une erreur 4xx est journalisée
avec le corps de la réponse (pour diagnostiquer précisément pourquoi
Groq refuse la requête) et abandonnée immédiatement, sans retry inutile.
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

_TIMEOUT_SECONDS = 45  # augmenté (30s trop court, timeout d'écriture observé en conditions réelles)
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
même si la qualité est moyenne (photo, scan incliné, léger flou), et extrait
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

RÈGLES D'EXTRACTION :
- numero_piece : UNIQUEMENT le numéro de référence explicite du document (ex: après "Facture n°", "Facture #", "N°", "Invoice"). NE JAMAIS utiliser un nom de personne, d'entreprise ou de cabinet comme numéro de pièce.
- montant_ht / montant_tva / montant_ttc : nombres décimaux (ex: 1234.50), jamais de texte, jamais de symbole monétaire.
- Si le document affiche "Sous-total" (ou équivalent), traite-le comme montant_ht.
- Si taux_tva = 0 (ou "TVA 0%"), alors montant_ht DOIT être égal à montant_ttc (déduis-le si besoin).
- Si un seul montant total (TTC) est visible avec un taux de TVA non nul, tu PEUX déduire HT et TVA par le calcul (HT = TTC / (1 + taux/100)).
- date_piece : uniquement au format YYYY-MM-DD. Si ambiguë ou absente, laisse null.
- Ne JAMAIS inventer une valeur : si un champ n'est pas identifiable dans l'image, renvoie null.
- ICE = 15 chiffres, IF = 6-8 chiffres, RC = 3-8 chiffres -- uniquement des identifiants marocains standards, jamais un numéro de téléphone ou de compte bancaire.

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


# Détermine si une exception justifie un nouvel essai : timeout et
# coupure de connexion (réseau instable, se corrige souvent tout
# seul), ou erreur serveur 5xx (Groq temporairement surchargé). Une
# erreur 4xx (requête mal formée, clé invalide, modèle inconnu...) ne
# se corrige JAMAIS en réessayant à l'identique -- inutile d'attendre.
def _erreur_est_transitoire(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


# Effectue l'appel HTTP réel à l'API vision Groq pour UNE image, avec
# retry limité aux erreurs transitoires (voir _erreur_est_transitoire).
# Journalise le corps de la réponse en cas d'erreur HTTP, pour
# diagnostiquer précisément la cause (modèle invalide, payload
# rejeté...) plutôt que de deviner.
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
        
        # --- MODIFICATION ICI : 1024 -> 2048 pour éviter de couper le JSON ---
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


# Point d'entrée principal : lit UNE page, l'envoie au modèle vision
# Groq, retourne le dict au format pipeline standard -- ou None en cas
# d'échec définitif.
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
    return donnees