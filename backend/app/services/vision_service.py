"""
app/services/vision_service.py

Service d'extraction Vision pour ComptaFlow.

Objectifs :
- utiliser Groq Vision comme chemin principal ;
- classifier ET extraire le document dans un seul appel ;
- prendre en charge facture, relevé bancaire, CNSS, TVA,
  chèque et autres documents ;
- éviter le second appel Groq sur la première page bancaire ;
- rester sous le quota TPM actuel grâce à un prompt compact ;
- laisser PaddleOCR / texte natif / Ollama comme fallback
  si Vision échoue.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import requests

from app.core.config import settings
from app.services.accounting_rules_service import (
    normaliser_nature_economique_extraite,
)
from app.services.extraction_mapping_service import construire_donnees_extraites


logger = logging.getLogger(
    "comptaflow.vision_service"
)


# ============================================================
# CONFIGURATION GROQ
# ============================================================

_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

_MODELE_VISION = "qwen/qwen3.6-27b"

_TIMEOUT_SECONDS = 60

_NOMBRE_TENTATIVES = 2

_DELAI_ENTRE_TENTATIVES_SEC = 1.5


# Le précédent :
#
# max_completion_tokens = 8192
#
# faisait dépasser la limite TPM actuelle de ton compte.
#
# On garde maintenant suffisamment de place pour
# les lignes d'un relevé bancaire tout en restant
# beaucoup plus raisonnable.
_MAX_COMPLETION_TOKENS = 3800


# ============================================================
# SCHÉMA JSON COMPACT
# ============================================================

_SCHEMA_JSON = """
{
  "nom_fournisseur": null,
  "ice_fournisseur": null,
  "if_fournisseur": null,
  "rc_fournisseur": null,

  "nom_client": null,
  "ice_client": null,
  "if_client": null,
  "rc_client": null,

  "categorie_document":
    "facture|releve_bancaire|avis_cnss|avis_tva|autre",

  "sous_type_document": null,

  "date_piece": null,
  "numero_piece": null,

  "nature_comptable": null,

  "devise": null,
  "montant_document": null,

  "montant_ht": null,
  "taux_tva": null,
  "montant_tva": null,
  "montant_ttc": null,

  "banque": null,
  "titulaire_compte": null,
  "rib": null,

  "periode_debut": null,
  "periode_fin": null,

  "solde_depart": null,
  "solde_final": null,

  "total_debit_imprime": null,
  "total_credit_imprime": null,

  "nombre_lignes_detectees": null,

  "lignes_bancaires": [
    {
      "code_operation": null,
      "date_operation": null,
      "date_valeur": null,
      "libelle_original": null,
      "reference": null,
      "devise": null,
      "debit": null,
      "credit": null,
      "solde_apres_operation": null,
      "texte_brut": null
    }
  ]
}
""".strip()


# ============================================================
# PROMPT GROQ VISION
# ============================================================

_PROMPT_TEXTE = f"""
Analyse UNE PAGE d'un document comptable marocain.

Réponds UNIQUEMENT avec un JSON valide.
Pas de markdown.
Pas de commentaire.
Pas de texte avant ou après le JSON.

N'invente jamais une donnée illisible :
utilise null.


CLASSIFICATION

categorie_document doit être exactement :

facture
releve_bancaire
avis_cnss
avis_tva
autre


Si le document appartient à un autre type,
utilise sous_type_document.

Exemples :

cheque
recu
avis_debit
avis_credit
justificatif_paiement
document_fiscal
ordre_virement
rib_seul
bordereau
autre_document


FACTURE

Ne décide PAS si la facture est un achat
ou une vente.

ComptaFlow le déterminera plus tard
avec l'entreprise du cabinet.

Sépare toujours :

FOURNISSEUR / EMETTEUR

et

CLIENT / DESTINATAIRE.


Extrais si visibles :

nom_fournisseur
ice_fournisseur
if_fournisseur
rc_fournisseur

nom_client
ice_client
if_client
rc_client

date_piece
numero_piece

devise

Pour devise, retourne si possible un code court :
MAD, EUR, USD, CAD, GBP, CHF, SAR, KWD, AED, QAR, BHD, JPY ou OMR.
N'invente jamais la devise si elle n'est pas visible.

montant_ht
taux_tva
montant_ttc
montant_tva

Pour une FACTURE uniquement, renseigne aussi nature_comptable.

nature_comptable doit être exactement UNE valeur parmi :

# Natures utilisables pour achats et/ou ventes
marchandises_revendues
matieres_premieres
fournitures_consommables
emballages
eau_electricite
entretien_non_stocke
petit_outillage_non_immobilise
fournitures_bureau
travaux_sous_traitance
etudes_sous_traitance
prestations_sous_traitance
location
credit_bail
entretien_reparation
assurance
honoraires
transport
deplacement_mission_reception
publicite
telecom_poste
services_bancaires
materiel_outillage
vehicule_transport
mobilier_bureau
materiel_informatique

# Natures particulièrement utiles pour les ventes
produits_finis
produits_intermediaires
produits_residuels
travaux
etudes
prestations_service
redevances
locations_accessoires
ports_frais_accessoires_factures
produits_accessoires

Règles pour nature_comptable :
- décris la NATURE économique visible, jamais un numéro de compte ;
- ne décide jamais achat/vente ici : ComptaFlow le décide ensuite selon
  l'entreprise suivie et le rôle fournisseur/client ;
- si une facture porte clairement sur des travaux, études ou prestations
  vendus, préfère travaux, etudes ou prestations_service ;
- si elle porte sur des biens fabriqués par l'émetteur, utilise
  produits_finis / produits_intermediaires / produits_residuels selon
  ce qui est explicitement identifiable ;
- si plusieurs natures importantes apparaissent et qu'aucune ne domine,
  utilise null ;
- pour un bien durable clairement identifiable (ordinateur, mobilier,
  véhicule, machine/outillage durable), utilise la nature durable
  correspondante ; ComptaFlow décidera ensuite si une validation humaine
  est nécessaire ;
- pour tout document non facture : nature_comptable = null.


ICE marocain = exactement 15 chiffres.

Ne mélange jamais les identifiants
du fournisseur avec ceux du client.


RELEVE BANCAIRE

Si categorie_document = releve_bancaire :

Extrais DIRECTEMENT toutes les opérations
visibles dans lignes_bancaires.

Cette extraction doit être faite dans
CE PREMIER APPEL.

Ne demande pas un deuxième traitement.


Pour les opérations :

- conserve chaque ligne ;
- respecte l'ordre visuel ;
- ne fusionne jamais deux lignes ;
- ne déduplique jamais ;
- ne supprime jamais une ligne répétée.


Pour chaque ligne extrais :

code_operation
date_operation
date_valeur
libelle_original
reference
devise
debit
credit
solde_apres_operation
texte_brut


IMPORTANT :

debit = uniquement le montant visible
dans la colonne DEBIT.

credit = uniquement le montant visible
dans la colonne CREDIT.


Une opération possède au maximum :

un débit

OU

un crédit.


Si une ligne est partiellement illisible :

conserve la ligne

et mets uniquement les champs illisibles
à null.


texte_brut doit retranscrire le contenu
visible de la ligne.


NE PAS mettre dans lignes_bancaires :

solde de départ
solde final
total débit
total crédit
en-têtes


Extrais séparément :

banque
titulaire_compte
rib
devise

Pour un relevé en devise, devise = devise du compte/relevé si elle est visible.
Si une opération affiche explicitement une autre devise, renseigne aussi
le champ devise de cette ligne.

periode_debut
periode_fin

solde_depart
solde_final

total_debit_imprime
total_credit_imprime

nombre_lignes_detectees


Pour un relevé bancaire :

montant_document = null
montant_ht = null
taux_tva = null
montant_tva = null
montant_ttc = null


CHEQUE

Si le document est un chèque :

categorie_document = "autre"

sous_type_document = "cheque"


Si visible :

numero_piece = numéro du chèque

date_piece = date

montant_document = montant

devise = devise


Ne mets jamais le montant du chèque
dans montant_ttc.


AUTRES DOCUMENTS

Pour :

reçu
avis bancaire
avis débit
avis crédit
justificatif
bordereau
ordre de virement
document fiscal
autre document

utilise :

categorie_document = "autre"

et renseigne :

sous_type_document


Si un montant principal est clairement visible :

montant_document = ce montant.


REGLES

Dates :

YYYY-MM-DD


Montants :

nombres uniquement.

Pas de symbole monétaire.


Pour l'instant :

ignore les annotations manuscrites.

Ignore les tampons ajoutés après impression.


Si un champ n'est pas applicable :

null


Si une information est incertaine :

null


Pour tout document non bancaire :

lignes_bancaires = []


Schéma exact :

{_SCHEMA_JSON}
""".strip()


# ============================================================
# IMAGE -> BASE64
# ============================================================

def _encoder_image_base64(
    chemin_image: str,
) -> str:
    """
    Encode une image locale en Base64.
    """

    with open(
        chemin_image,
        "rb",
    ) as fichier:

        contenu = fichier.read()

    return base64.b64encode(
        contenu
    ).decode(
        "utf-8"
    )


# ============================================================
# PARSER JSON
# ============================================================

def _nettoyer_et_parser_json(
    texte_reponse: str,
) -> dict[str, Any] | None:
    """
    Nettoie la réponse Groq puis récupère
    le premier objet JSON complet.
    """

    if not texte_reponse:
        return None


    nettoye = (
        texte_reponse
        .replace(
            "```json",
            "",
        )
        .replace(
            "```JSON",
            "",
        )
        .replace(
            "```",
            "",
        )
        .strip()
    )


    debut = nettoye.find(
        "{"
    )

    fin = nettoye.rfind(
        "}"
    )


    if (
        debut == -1
        or fin == -1
        or fin < debut
    ):

        logger.warning(
            "Groq Vision : "
            "aucun objet JSON détecté."
        )

        return None


    bloc_json = nettoye[
        debut:
        fin + 1
    ]


    try:

        parsed = json.loads(
            bloc_json
        )

    except json.JSONDecodeError as exc:

        logger.warning(
            "Groq Vision : JSON invalide : %s",
            exc,
        )

        return None


    if not isinstance(
        parsed,
        dict,
    ):

        return None


    return parsed


# ============================================================
# ERREURS TRANSITOIRES
# ============================================================

def _erreur_est_transitoire(
    exc: Exception,
) -> bool:
    """
    Détermine si un retry peut réellement
    être utile.

    413 n'est volontairement PAS retry :
    le payload doit d'abord être réduit.
    """

    if isinstance(
        exc,
        (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ),
    ):

        return True


    if (
        isinstance(
            exc,
            requests.exceptions.HTTPError,
        )
        and exc.response is not None
    ):

        code = (
            exc.response.status_code
        )


        # 408 : timeout
        # 429 : quota temporaire
        # 5xx : problème serveur
        return (
            code in {
                408,
                429,
            }
            or code >= 500
        )


    return False


# ============================================================
# APPEL GROQ
# ============================================================

def _appeler_groq_vision_avec_retry(
    image_b64: str,
) -> str | None:
    """
    Appelle Groq Vision.

    Corrections importantes :

    - UN seul appel Vision ;
    - pas de response_format=json_object ;
    - prompt compact ;
    - reasoning_effort=none ;
    - max_completion_tokens limité ;
    - pas de retry inutile sur erreur 413.
    """

    corps = {

        "model":
            _MODELE_VISION,


        "messages": [
            {
                "role":
                    "user",

                "content": [

                    {
                        "type":
                            "text",

                        "text":
                            _PROMPT_TEXTE,
                    },

                    {
                        "type":
                            "image_url",

                        "image_url": {

                            "url":
                                (
                                    "data:image/png;base64,"
                                    f"{image_b64}"
                                )
                        },
                    },
                ],
            }
        ],


        # Pour une extraction structurée,
        # pas besoin d'un raisonnement long.
        "reasoning_effort":
            "none",


        "temperature":
            0.1,


        # IMPORTANT :
        # anciennement 8192 -> dépassement TPM.
        "max_completion_tokens":
            _MAX_COMPLETION_TOKENS,
    }


    headers = {

        "Authorization":
            (
                f"Bearer "
                f"{settings.GROQ_API_KEY}"
            ),

        "Content-Type":
            "application/json",
    }


    for tentative in range(
        1,
        _NOMBRE_TENTATIVES + 1,
    ):

        try:

            reponse = requests.post(
                _URL,
                headers=headers,
                json=corps,
                timeout=_TIMEOUT_SECONDS,
            )


            reponse.raise_for_status()


            contenu = (
                reponse.json()
            )


            return (
                contenu[
                    "choices"
                ][0][
                    "message"
                ][
                    "content"
                ]
            )


        except (
            requests.exceptions.RequestException,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as exc:

            corps_reponse = ""


            if (
                isinstance(
                    exc,
                    requests.exceptions.HTTPError,
                )
                and exc.response is not None
            ):

                corps_reponse = (
                    " | Réponse serveur : "
                    f"{exc.response.text[:500]}"
                )


            # --------------------------------------------
            # RETRY SEULEMENT SI ÇA A DU SENS
            # --------------------------------------------

            if (
                _erreur_est_transitoire(
                    exc
                )
                and tentative
                < _NOMBRE_TENTATIVES
            ):

                logger.warning(
                    "Appel Groq vision échoué "
                    "(tentative %s/%s, transitoire), "
                    "retry dans %ss : %s%s",
                    tentative,
                    _NOMBRE_TENTATIVES,
                    _DELAI_ENTRE_TENTATIVES_SEC,
                    exc,
                    corps_reponse,
                )


                time.sleep(
                    _DELAI_ENTRE_TENTATIVES_SEC
                )


                continue


            logger.warning(
                "Appel Groq vision définitivement "
                "échoué (tentative %s/%s) : %s%s",
                tentative,
                _NOMBRE_TENTATIVES,
                exc,
                corps_reponse,
            )


            return None


    return None


# ============================================================
# CONVERSION NOMBRE
# ============================================================

def _vers_float(
    valeur: Any,
) -> float | None:
    """
    Convertit une valeur reçue de l'IA
    vers un float quand possible.
    """

    if valeur is None:
        return None


    if isinstance(
        valeur,
        (
            int,
            float,
        ),
    ):

        return float(
            valeur
        )


    if isinstance(
        valeur,
        str,
    ):

        propre = (
            valeur
            .strip()
            .replace(
                "\u00a0",
                "",
            )
            .replace(
                " ",
                "",
            )
        )


        if not propre:
            return None


        # Format français :
        # 1.234,56
        if (
            "," in propre
            and "." in propre
        ):

            propre = (
                propre
                .replace(
                    ".",
                    "",
                )
                .replace(
                    ",",
                    ".",
                )
            )


        # Format :
        # 1234,56
        elif "," in propre:

            propre = (
                propre.replace(
                    ",",
                    ".",
                )
            )


        try:

            return float(
                propre
            )

        except ValueError:

            return None


    return None


# ============================================================
# NORMALISATION NATURE COMPTABLE
# ============================================================

def _normaliser_nature_comptable(
    valeur: Any,
) -> str | None:
    return normaliser_nature_economique_extraite(valeur)


# ============================================================
# NORMALISATION TYPE
# ============================================================

def _normaliser_categorie_document(
    valeur: Any,
) -> str:
    """
    Empêche Groq d'inventer une catégorie
    principale non prévue.

    Les types supplémentaires passent par
    sous_type_document.
    """

    normalisee = str(
        valeur
        or "autre"
    ).strip().lower()


    autorisees = {

        "facture",

        "releve_bancaire",

        "avis_cnss",

        "avis_tva",

        "autre",
    }


    if normalisee not in autorisees:

        return "autre"


    return normalisee


# ============================================================
# VALIDATION MONTANTS FACTURE
# ============================================================

def _valider_et_corriger_montants(
    donnees: dict[str, Any],
) -> dict[str, Any]:
    """
    Contrôle les montants extraits SANS les recalculer.

    Règles :
    - HT / TVA / TTC restent exactement les valeurs extraites ;
    - aucune valeur manquante n'est reconstruite ;
    - HT + TVA ~= TTC est uniquement un contrôle ;
    - si le taux est disponible, HT * taux ~= TVA est aussi contrôlé ;
    - une incohérence marque a_verifier mais ne modifie aucun montant.
    """

    if not donnees:
        return donnees

    if (
        donnees.get("type_document") == "releve_bancaire"
        or donnees.get("categorie_document") == "releve_bancaire"
    ):
        donnees["montant_ht"] = None
        donnees["montant_tva"] = None
        donnees["montant_ttc"] = None
        donnees["taux_tva"] = None
        donnees["montant_document"] = None
        return donnees

    ht = _vers_float(donnees.get("montant_ht"))
    tva = _vers_float(donnees.get("montant_tva"))
    ttc = _vers_float(donnees.get("montant_ttc"))
    taux = _vers_float(donnees.get("taux_tva"))

    donnees["montant_ht"] = ht
    donnees["montant_tva"] = tva
    donnees["montant_ttc"] = ttc
    donnees["taux_tva"] = taux

    raisons: list[str] = []

    ancienne_raison = str(
        donnees.get("raison_verification")
        or ""
    ).strip()

    if ancienne_raison:
        raisons.append(ancienne_raison)

    if ht is not None and tva is not None and ttc is not None:
        ecart_total = abs((ht + tva) - ttc)

        if ecart_total > 1.0:
            raisons.append(
                "Incohérence montants extraits : "
                f"HT ({ht:.2f}) + TVA ({tva:.2f}) != TTC ({ttc:.2f})."
            )

    if ht is not None and tva is not None and taux is not None:
        tva_attendue = ht * (taux / 100.0)
        ecart_tva = abs(tva_attendue - tva)

        if ecart_tva > 1.0:
            raisons.append(
                "Incohérence taux TVA extrait : "
                f"HT ({ht:.2f}) x {taux:g}% donne {tva_attendue:.2f}, "
                f"mais TVA extraite = {tva:.2f}."
            )

    # Déduplication tout en conservant l'ordre.
    raisons_uniques: list[str] = []
    for raison in raisons:
        if raison and raison not in raisons_uniques:
            raisons_uniques.append(raison)

    if raisons_uniques:
        donnees["a_verifier"] = True
        donnees["raison_verification"] = " | ".join(raisons_uniques)
    else:
        donnees["a_verifier"] = bool(donnees.get("a_verifier"))
        if not donnees["a_verifier"]:
            donnees["raison_verification"] = None

    return donnees


# ============================================================
# CONSTRUCTION PAGE BANCAIRE
# ============================================================

def _construire_page_bancaire(
    champs: dict[str, Any],
) -> dict[str, Any]:
    """
    Prépare les données bancaires pour :

    bank_statement_service
    .normaliser_et_valider_releve()

    On ne déduplique aucune ligne.
    """

    lignes_brutes = (
        champs.get(
            "lignes_bancaires"
        )
    )


    if not isinstance(
        lignes_brutes,
        list,
    ):

        lignes_brutes = []


    lignes: list[
        dict[str, Any]
    ] = []


    for ligne in lignes_brutes:

        if not isinstance(
            ligne,
            dict,
        ):

            continue


        debit = _vers_float(
            ligne.get(
                "debit"
            )
        )


        credit = _vers_float(
            ligne.get(
                "credit"
            )
        )


        # Une ligne ne doit jamais avoir
        # débit ET crédit en même temps.
        #
        # Si Groq produit les deux,
        # on ne devine pas lequel est juste.

        if (
            debit is not None
            and credit is not None
        ):

            debit = None

            credit = None


        lignes.append(
            {

                "code_operation":
                    ligne.get(
                        "code_operation"
                    ),


                "date_operation":
                    ligne.get(
                        "date_operation"
                    ),


                "date_valeur":
                    ligne.get(
                        "date_valeur"
                    ),


                "libelle_original":
                    ligne.get(
                        "libelle_original"
                    ),


                "reference":
                    ligne.get(
                        "reference"
                    ),


                "devise":
                    (
                        ligne.get("devise")
                        or champs.get("devise")
                    ),


                "debit":
                    debit,


                "credit":
                    credit,


                "solde_apres_operation":
                    _vers_float(
                        ligne.get(
                            "solde_apres_operation"
                        )
                    ),


                "texte_brut":
                    ligne.get(
                        "texte_brut"
                    ),
            }
        )


    return {

        "type_document":
            "releve_bancaire",


        "categorie_document":
            "releve_bancaire",


        "categorie":
            "banque",


        "sous_type_document":
            champs.get(
                "sous_type_document"
            ),


        "banque":
            champs.get(
                "banque"
            ),


        "titulaire_compte":
            champs.get(
                "titulaire_compte"
            ),


        "rib":
            champs.get(
                "rib"
            ),


        "periode_debut":
            champs.get(
                "periode_debut"
            ),


        "periode_fin":
            champs.get(
                "periode_fin"
            ),


        "solde_depart":
            _vers_float(
                champs.get(
                    "solde_depart"
                )
            ),


        "solde_final":
            _vers_float(
                champs.get(
                    "solde_final"
                )
            ),


        "total_debit_imprime":
            _vers_float(
                champs.get(
                    "total_debit_imprime"
                )
            ),


        "total_credit_imprime":
            _vers_float(
                champs.get(
                    "total_credit_imprime"
                )
            ),


        "nombre_lignes_detectees":
            champs.get(
                "nombre_lignes_detectees"
            ),


        "lignes_bancaires":
            lignes,


        "date_piece":
            (
                champs.get(
                    "date_piece"
                )
                or
                champs.get(
                    "periode_fin"
                )
            ),


        "nom_entreprise":
            champs.get(
                "titulaire_compte"
            ),


        "tiers":
            None,


        "montant_ht":
            None,


        "taux_tva":
            None,


        "montant_tva":
            None,


        "montant_ttc":
            None,


        "montant_document":
            None,


        "devise":
            champs.get(
                "devise"
            ),


        "source_extraction":
            "groq_vision_unifiee",
    }


# ============================================================
# EXTRACTION PUBLIQUE
# ============================================================

def extraire_et_classifier_depuis_image(
    chemin_image: str,
) -> dict[str, Any] | None:
    """
    Classe ET extrait une page dans
    UN SEUL appel Groq Vision.

    Relevé bancaire :
    retourne directement les transactions.

    Facture / CNSS / TVA / chèque / autre :
    retourne les champs structurés.

    Si Vision échoue :
    retourne None.

    document_processing.py déclenchera alors
    le fallback texte natif / PaddleOCR.
    """

    # --------------------------------------------------------
    # GROQ NON CONFIGURÉ
    # --------------------------------------------------------

    if not settings.GROQ_API_KEY:

        logger.info(
            "Groq Vision ignoré : "
            "GROQ_API_KEY absente."
        )

        return None


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    try:

        image_b64 = (
            _encoder_image_base64(
                chemin_image
            )
        )


    except OSError as exc:

        logger.warning(
            "Lecture image impossible "
            "pour Groq Vision : %s",
            exc,
        )

        return None


    # --------------------------------------------------------
    # GROQ
    # --------------------------------------------------------

    texte_json = (
        _appeler_groq_vision_avec_retry(
            image_b64
        )
    )


    if texte_json is None:

        return None


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    champs = (
        _nettoyer_et_parser_json(
            texte_json
        )
    )


    if champs is None:

        logger.warning(
            "Réponse Groq Vision "
            "non-JSON exploitable -- "
            "fallback requis."
        )

        return None


    # --------------------------------------------------------
    # CATÉGORIE
    # --------------------------------------------------------

    categorie_document = (
        _normaliser_categorie_document(
            champs.get(
                "categorie_document"
            )
        )
    )


    champs[
        "categorie_document"
    ] = categorie_document


    # ========================================================
    # RELEVÉ BANCAIRE
    # ========================================================

    if (
        categorie_document
        == "releve_bancaire"
    ):

        return (
            _construire_page_bancaire(
                champs
            )
        )


    # ========================================================
    # AUTRES DOCUMENTS
    # ========================================================

    donnees = (
        construire_donnees_extraites(
            champs
        )
    )


    # IMPORTANT : la fonction historique _construire_donnees peut
    # compléter certains montants. Pour le chemin Vision, on restaure
    # toujours les valeurs réellement renvoyées par l'extraction afin
    # de respecter la règle métier : ne jamais remplacer HT / TVA / TTC
    # par un calcul silencieux.
    for champ_montant in (
        "montant_ht",
        "taux_tva",
        "montant_tva",
        "montant_ttc",
    ):
        donnees[champ_montant] = _vers_float(
            champs.get(champ_montant)
        )


    # Nature économique contrôlée de la facture.
    # Groq ne fournit jamais de numéro de compte : seulement une nature
    # que le moteur Python convertira ensuite en règle CGNC.
    donnees["nature_comptable"] = (
        _normaliser_nature_comptable(
            champs.get("nature_comptable")
        )
        if categorie_document == "facture"
        else None
    )


    # Type physique détecté.
    donnees[
        "type_document"
    ] = categorie_document


    donnees[
        "categorie_document"
    ] = categorie_document


    donnees[
        "sous_type_document"
    ] = champs.get(
        "sous_type_document"
    )


    donnees[
        "devise"
    ] = champs.get(
        "devise"
    )


    donnees[
        "montant_document"
    ] = _vers_float(
        champs.get(
            "montant_document"
        )
    )


    donnees[
        "source_extraction"
    ] = "groq_vision"


    # --------------------------------------------------------
    # CONTRÔLE FACTURE
    # --------------------------------------------------------

    return (
        _valider_et_corriger_montants(
            donnees
        )
    )
