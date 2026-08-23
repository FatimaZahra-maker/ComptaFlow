"""
app/services/document_classifier.py

Classifieur local de secours utilisé lorsque Groq Vision est indisponible.

Règle importante : une facture peut contenir un RIB, un IBAN et le nom d'une
banque. Ces seuls éléments ne suffisent JAMAIS à transformer la facture en
relevé bancaire.
"""
from __future__ import annotations

import unicodedata


def _normaliser(texte: str) -> str:
    texte = (texte or "").lower()
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texte)
        if unicodedata.category(caractere) != "Mn"
    )


_MOTS_CLES = {
    "avis_cnss": [
        "cnss",
        "caisse nationale de securite sociale",
        "affiliation",
        "cotisation",
        "salarie",
        "bordereau de paiement",
    ],
    "avis_tva": [
        "declaration de tva",
        "taxe sur la valeur ajoutee",
        "avis d'imposition",
        "direction generale des impots",
        "chiffre d'affaires imposable",
    ],
    "releve_bancaire": [
        "releve de compte",
        "releve bancaire",
        "solde initial",
        "solde final",
        "date valeur",
        "date operation",
        "debit",
        "credit",
    ],
    "facture": [
        "facture",
        "invoice",
        "numero facture",
        "n facture",
        "total ht",
        "total ttc",
        "montant ht",
        "montant ttc",
        "tva",
    ],
}

# Les mots suivants existent fréquemment SUR UNE FACTURE et ne doivent donc
# jamais suffire seuls à classer le document comme relevé bancaire.
_MOTS_BANCAIRES_FAIBLES = [
    "iban",
    "rib",
    "banque populaire",
    "attijariwafa",
    "bank of africa",
    "bmce",
    "cih bank",
    "societe generale",
]

_MARQUEURS_FACTURE_FORTS = [
    "facture",
    "invoice",
]

_MARQUEURS_TOTAL_FACTURE = [
    "total ht",
    "total ttc",
    "montant ht",
    "montant ttc",
    "net a payer",
]

_MARQUEURS_RELEVE_FORTS = [
    "releve de compte",
    "releve bancaire",
]

_MARQUEURS_STRUCTURE_BANQUE = [
    "solde initial",
    "solde final",
    "date valeur",
    "date operation",
    "debit",
    "credit",
]


def _compter(texte: str, expressions: list[str]) -> int:
    return sum(1 for expression in expressions if expression in texte)


def detecter_type_document(texte_ocr: str) -> str:
    """
    Retourne : facture / releve_bancaire / avis_cnss / avis_tva / autre.

    Priorités de sécurité :
    1. documents fiscaux explicites ;
    2. facture explicite ;
    3. relevé bancaire seulement avec marqueurs de structure forts ;
    4. score de secours.
    """
    if not texte_ocr or not texte_ocr.strip():
        return "autre"

    texte = _normaliser(texte_ocr)

    # CNSS explicite.
    if (
        "caisse nationale de securite sociale" in texte
        or (
            "cnss" in texte
            and _compter(texte, _MOTS_CLES["avis_cnss"]) >= 2
        )
    ):
        return "avis_cnss"

    # TVA / DGI explicite.
    if (
        "declaration de tva" in texte
        or "chiffre d'affaires imposable" in texte
        or (
            "direction generale des impots" in texte
            and "tva" in texte
        )
    ):
        return "avis_tva"

    # Une facture qui affiche aussi un RIB/IBAN reste une facture.
    facture_forte = _compter(texte, _MARQUEURS_FACTURE_FORTS) >= 1
    total_facture = _compter(texte, _MARQUEURS_TOTAL_FACTURE) >= 1
    if facture_forte and (total_facture or "tva" in texte):
        return "facture"

    # Relevé bancaire : marqueur explicite ou plusieurs éléments de structure.
    if _compter(texte, _MARQUEURS_RELEVE_FORTS) >= 1:
        return "releve_bancaire"

    if _compter(texte, _MARQUEURS_STRUCTURE_BANQUE) >= 3:
        return "releve_bancaire"

    # Score de secours. Les mots bancaires faibles ne sont volontairement pas
    # utilisés ici : RIB/IBAN/nom de banque sont courants sur une facture.
    scores = {
        type_document: _compter(texte, mots_cles)
        for type_document, mots_cles in _MOTS_CLES.items()
    }

    meilleur_type = max(scores, key=scores.get)
    meilleur_score = scores[meilleur_type]

    if meilleur_score == 0:
        # On lit quand même les faibles marqueurs pour les logs/debug futurs,
        # mais ils ne suffisent pas à classer Banque.
        _ = _compter(texte, _MOTS_BANCAIRES_FAIBLES)
        return "autre"

    return meilleur_type
