"""
app/services/document_classifier.py

Détection du type de document par mots-clés, en Python pur — instantané,
sans coût de temps ni dépendance IA. Les 5 types retournés doivent
correspondre exactement aux clés de EXTRACTION_PROMPTS dans
ai_service.py : "facture", "releve_bancaire", "avis_cnss", "avis_tva",
"autre".

Principe : on score chaque type selon le nombre de mots-clés trouvés
dans le texte OCR, et on retourne le type avec le score le plus élevé.
"autre" est le repli par défaut si aucun mot-clé ne matche.
"""
import re

# Mots-clés par type, en minuscules (comparaison insensible à la casse).
# Plus un document contient de mots-clés d'un type, plus son score monte.
_MOTS_CLES = {
    "avis_cnss": [
        "cnss",
        "caisse nationale de sécurité sociale",
        "affiliation",
        "cotisation",
        "salarié",
        "bordereau de paiement",
    ],
    "avis_tva": [
        "déclaration de tva",
        "taxe sur la valeur ajoutée",
        "avis d'imposition",
        "direction générale des impôts",
        "dgi",
        "chiffre d'affaires imposable",
    ],
    "releve_bancaire": [
        "relevé de compte",
        "relevé bancaire",
        "solde initial",
        "solde final",
        "iban",
        "rib",
        "banque populaire",
        "attijariwafa",
        "bmce",
        "cih bank",
        "société générale",
    ],
    "facture": [
        "facture",
        "invoice",
        "bon de commande",
        "bon de livraison",
        "total ht",
        "total ttc",
        "total general",
        "total général",
        "montant ttc",
    ],
}

# Ordre de priorité en cas d'égalité de score : un avis CNSS/TVA mal
# détecté comme facture est plus gênant qu'une facture mal détectée
# comme "autre", donc on les priorise.
_ORDRE_PRIORITE = ["avis_cnss", "avis_tva", "releve_bancaire", "facture"]


def detecter_type_document(texte_ocr: str) -> str:
    """
    Retourne le type de document détecté parmi :
    "facture", "releve_bancaire", "avis_cnss", "avis_tva", "autre".

    Score chaque type par nombre de mots-clés trouvés (insensible à la
    casse et aux accents basiques), retient le meilleur score. En cas
    d'égalité, applique _ORDRE_PRIORITE. Si aucun mot-clé ne matche,
    retourne "autre".
    """
    if not texte_ocr:
        return "autre"

    texte_normalise = texte_ocr.lower()

    scores: dict[str, int] = {}
    for type_doc, mots_cles in _MOTS_CLES.items():
        score = 0
        for mot in mots_cles:
            if mot in texte_normalise:
                score += 1
        scores[type_doc] = score

    meilleur_score = max(scores.values())
    if meilleur_score == 0:
        return "autre"

    # Tous les types ayant le score maximal (en cas d'égalité)
    types_gagnants = [t for t, s in scores.items() if s == meilleur_score]

    if len(types_gagnants) == 1:
        return types_gagnants[0]

    # Égalité : on applique l'ordre de priorité
    for type_prioritaire in _ORDRE_PRIORITE:
        if type_prioritaire in types_gagnants:
            return type_prioritaire

    # Filet de sécurité, ne devrait jamais être atteint
    return types_gagnants[0]