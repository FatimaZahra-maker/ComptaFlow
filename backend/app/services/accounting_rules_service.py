"""
app/services/accounting_rules_service.py

Règles déterministes de classement comptable des ACHATS et des VENTES.

Principes :
- l'IA propose uniquement une NATURE économique contrôlée ;
- Python transforme cette nature en famille CGNC ;
- Python n'invente jamais un numéro Topaze complet ;
- le compte exact vient du plan comptable de l'entreprise ou d'un
  historique déjà confirmé ;
- les montants HT / TVA / TTC restent ceux extraits de la pièce.

Pour les achats durables (matériel, mobilier, véhicule...), le moteur
conserve le statut ``immobilisation_candidate`` tant que la politique
exacte du cabinet n'est pas configurée.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal


TraitementComptable = Literal[
    "charge",
    "immobilisation_candidate",
]


@dataclass(frozen=True)
class RegleCompteHT:
    nature: str
    libelle: str
    famille_cgnc: str
    traitement: TraitementComptable


@dataclass(frozen=True)
class RegleCompteVente:
    nature: str
    libelle: str
    famille_cgnc: str


# ============================================================
# ACHATS
# ============================================================

REGLES_ACHAT: dict[str, RegleCompteHT] = {
    "marchandises_revendues": RegleCompteHT(
        nature="marchandises_revendues",
        libelle="Achats de marchandises destinées à être revendues en l'état",
        famille_cgnc="6111",
        traitement="charge",
    ),
    "matieres_premieres": RegleCompteHT(
        nature="matieres_premieres",
        libelle="Achats de matières premières",
        famille_cgnc="6121",
        traitement="charge",
    ),
    "fournitures_consommables": RegleCompteHT(
        nature="fournitures_consommables",
        libelle="Achats de matières et fournitures consommables",
        famille_cgnc="6122",
        traitement="charge",
    ),
    "emballages": RegleCompteHT(
        nature="emballages",
        libelle="Achats d'emballages",
        famille_cgnc="6123",
        traitement="charge",
    ),
    "eau_electricite": RegleCompteHT(
        nature="eau_electricite",
        libelle="Achats non stockés - eau / électricité",
        famille_cgnc="61251",
        traitement="charge",
    ),
    "entretien_non_stocke": RegleCompteHT(
        nature="entretien_non_stocke",
        libelle="Fournitures d'entretien non stockées",
        famille_cgnc="61252",
        traitement="charge",
    ),
    "petit_outillage_non_immobilise": RegleCompteHT(
        nature="petit_outillage_non_immobilise",
        libelle="Petit outillage / petit équipement non immobilisé",
        famille_cgnc="61253",
        traitement="charge",
    ),
    "fournitures_bureau": RegleCompteHT(
        nature="fournitures_bureau",
        libelle="Fournitures de bureau non stockées",
        famille_cgnc="61254",
        traitement="charge",
    ),
    "travaux_sous_traitance": RegleCompteHT(
        nature="travaux_sous_traitance",
        libelle="Achats de travaux sous-traités",
        famille_cgnc="61261",
        traitement="charge",
    ),
    "etudes_sous_traitance": RegleCompteHT(
        nature="etudes_sous_traitance",
        libelle="Achats d'études sous-traitées",
        famille_cgnc="61262",
        traitement="charge",
    ),
    "prestations_sous_traitance": RegleCompteHT(
        nature="prestations_sous_traitance",
        libelle="Achats de prestations de service incorporées à l'activité",
        famille_cgnc="61263",
        traitement="charge",
    ),
    "location": RegleCompteHT(
        nature="location",
        libelle="Locations et charges locatives",
        famille_cgnc="6131",
        traitement="charge",
    ),
    "credit_bail": RegleCompteHT(
        nature="credit_bail",
        libelle="Redevances de crédit-bail",
        famille_cgnc="6132",
        traitement="charge",
    ),
    "entretien_reparation": RegleCompteHT(
        nature="entretien_reparation",
        libelle="Entretien et réparations courants",
        famille_cgnc="6133",
        traitement="charge",
    ),
    "assurance": RegleCompteHT(
        nature="assurance",
        libelle="Primes d'assurances",
        famille_cgnc="6134",
        traitement="charge",
    ),
    "honoraires": RegleCompteHT(
        nature="honoraires",
        libelle="Honoraires courants",
        famille_cgnc="61365",
        traitement="charge",
    ),
    "transport": RegleCompteHT(
        nature="transport",
        libelle="Transports",
        famille_cgnc="6142",
        traitement="charge",
    ),
    "deplacement_mission_reception": RegleCompteHT(
        nature="deplacement_mission_reception",
        libelle="Déplacements, missions et réceptions",
        famille_cgnc="6143",
        traitement="charge",
    ),
    "publicite": RegleCompteHT(
        nature="publicite",
        libelle="Publicité, publications et relations publiques",
        famille_cgnc="6144",
        traitement="charge",
    ),
    "telecom_poste": RegleCompteHT(
        nature="telecom_poste",
        libelle="Postes et télécommunications",
        famille_cgnc="6145",
        traitement="charge",
    ),
    "services_bancaires": RegleCompteHT(
        nature="services_bancaires",
        libelle="Services bancaires",
        famille_cgnc="6147",
        traitement="charge",
    ),
    "materiel_outillage": RegleCompteHT(
        nature="materiel_outillage",
        libelle="Matériel et outillage durable",
        famille_cgnc="2332",
        traitement="immobilisation_candidate",
    ),
    "vehicule_transport": RegleCompteHT(
        nature="vehicule_transport",
        libelle="Matériel de transport",
        famille_cgnc="2340",
        traitement="immobilisation_candidate",
    ),
    "mobilier_bureau": RegleCompteHT(
        nature="mobilier_bureau",
        libelle="Mobilier de bureau durable",
        famille_cgnc="2351",
        traitement="immobilisation_candidate",
    ),
    "materiel_informatique": RegleCompteHT(
        nature="materiel_informatique",
        libelle="Matériel informatique durable",
        famille_cgnc="2355",
        traitement="immobilisation_candidate",
    ),
}


_ALIASES_ACHAT: dict[str, str] = {
    "marchandise": "marchandises_revendues",
    "marchandises": "marchandises_revendues",
    "marchandises_revendues": "marchandises_revendues",
    "matiere_premiere": "matieres_premieres",
    "matieres_premieres": "matieres_premieres",
    "fourniture_consommable": "fournitures_consommables",
    "fournitures_consommables": "fournitures_consommables",
    "emballage": "emballages",
    "emballages": "emballages",
    "eau": "eau_electricite",
    "electricite": "eau_electricite",
    "eau_electricite": "eau_electricite",
    "entretien_non_stocke": "entretien_non_stocke",
    "petit_outillage": "petit_outillage_non_immobilise",
    "petit_outillage_non_immobilise": "petit_outillage_non_immobilise",
    "fourniture_bureau": "fournitures_bureau",
    "fournitures_bureau": "fournitures_bureau",
    "travaux": "travaux_sous_traitance",
    "travaux_sous_traitance": "travaux_sous_traitance",
    "etude": "etudes_sous_traitance",
    "etudes": "etudes_sous_traitance",
    "etudes_sous_traitance": "etudes_sous_traitance",
    "prestation": "prestations_sous_traitance",
    "prestations": "prestations_sous_traitance",
    "prestation_service": "prestations_sous_traitance",
    "prestations_service": "prestations_sous_traitance",
    "prestations_sous_traitance": "prestations_sous_traitance",
    "location": "location",
    "credit_bail": "credit_bail",
    "leasing": "credit_bail",
    "entretien_reparation": "entretien_reparation",
    "reparation": "entretien_reparation",
    "assurance": "assurance",
    "honoraires": "honoraires",
    "transport": "transport",
    "deplacement_mission_reception": "deplacement_mission_reception",
    "publicite": "publicite",
    "telecom_poste": "telecom_poste",
    "telecommunication": "telecom_poste",
    "services_bancaires": "services_bancaires",
    "materiel_outillage": "materiel_outillage",
    "vehicule": "vehicule_transport",
    "vehicule_transport": "vehicule_transport",
    "mobilier": "mobilier_bureau",
    "mobilier_bureau": "mobilier_bureau",
    "informatique": "materiel_informatique",
    "materiel_informatique": "materiel_informatique",
}


# ============================================================
# VENTES
# ============================================================

# Familles de produits utilisées par le moteur VENTE.
# Le compte exact à 12 chiffres reste propre au plan de l'entreprise.
REGLES_VENTE: dict[str, RegleCompteVente] = {
    "marchandises_revendues": RegleCompteVente(
        nature="marchandises_revendues",
        libelle="Ventes de marchandises au Maroc",
        famille_cgnc="7111",
    ),
    "produits_finis": RegleCompteVente(
        nature="produits_finis",
        libelle="Ventes de produits finis au Maroc",
        famille_cgnc="71211",
    ),
    "produits_intermediaires": RegleCompteVente(
        nature="produits_intermediaires",
        libelle="Ventes de produits intermédiaires au Maroc",
        famille_cgnc="71212",
    ),
    "produits_residuels": RegleCompteVente(
        nature="produits_residuels",
        libelle="Ventes de produits résiduels au Maroc",
        famille_cgnc="71217",
    ),
    "travaux": RegleCompteVente(
        nature="travaux",
        libelle="Ventes de travaux produits au Maroc",
        famille_cgnc="71241",
    ),
    "etudes": RegleCompteVente(
        nature="etudes",
        libelle="Ventes d'études produites au Maroc",
        famille_cgnc="71242",
    ),
    "prestations_service": RegleCompteVente(
        nature="prestations_service",
        libelle="Ventes de prestations de service produites au Maroc",
        famille_cgnc="71243",
    ),
    "redevances": RegleCompteVente(
        nature="redevances",
        libelle="Redevances pour brevets, marques, droits et valeurs similaires",
        famille_cgnc="7126",
    ),
    "locations_accessoires": RegleCompteVente(
        nature="locations_accessoires",
        libelle="Locations diverses reçues - produit accessoire",
        famille_cgnc="71271",
    ),
    "ports_frais_accessoires_factures": RegleCompteVente(
        nature="ports_frais_accessoires_factures",
        libelle="Ports et frais accessoires facturés",
        famille_cgnc="71276",
    ),
    "produits_accessoires": RegleCompteVente(
        nature="produits_accessoires",
        libelle="Autres ventes et produits accessoires",
        famille_cgnc="7127",
    ),
}


_ALIASES_VENTE: dict[str, str] = {
    "marchandise": "marchandises_revendues",
    "marchandises": "marchandises_revendues",
    "marchandises_revendues": "marchandises_revendues",
    "produit_fini": "produits_finis",
    "produits_finis": "produits_finis",
    "produit_intermediaire": "produits_intermediaires",
    "produits_intermediaires": "produits_intermediaires",
    "produit_residuel": "produits_residuels",
    "produits_residuels": "produits_residuels",
    "travaux": "travaux",
    "travaux_sous_traitance": "travaux",
    "etude": "etudes",
    "etudes": "etudes",
    "etudes_sous_traitance": "etudes",
    "prestation": "prestations_service",
    "prestations": "prestations_service",
    "prestation_service": "prestations_service",
    "prestations_service": "prestations_service",
    "prestations_sous_traitance": "prestations_service",
    "redevance": "redevances",
    "redevances": "redevances",
    "location_accessoire": "locations_accessoires",
    "locations_accessoires": "locations_accessoires",
    "port_frais_accessoires": "ports_frais_accessoires_factures",
    "ports_frais_accessoires": "ports_frais_accessoires_factures",
    "ports_frais_accessoires_factures": "ports_frais_accessoires_factures",
    "produit_accessoire": "produits_accessoires",
    "produits_accessoires": "produits_accessoires",
}


# ============================================================
# NORMALISATION COMMUNE
# ============================================================

def _normaliser_texte(valeur: object | None) -> str:
    if valeur is None:
        return ""

    text = str(valeur).strip().lower()
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )

    for caractere in ("-", "/", "\\", ".", ",", ";", ":", "(", ")"):
        text = text.replace(caractere, " ")

    return "_".join(text.split())


NATURES_ECONOMIQUES_AUTORISEES = frozenset(
    set(REGLES_ACHAT) | set(REGLES_VENTE)
)


def normaliser_nature_economique_extraite(
    valeur: object | None,
) -> str | None:
    """Valide la nature brute sans décider encore Achat ou Vente.

    Vision, Groq texte et Ollama doivent partager exactement le même
    vocabulaire. La conversion vers une règle Achat/Vente reste effectuée
    plus tard, une fois l'entreprise gérée et le sens de la facture connus.
    """
    normalisee = _normaliser_texte(valeur)
    return (
        normalisee
        if normalisee in NATURES_ECONOMIQUES_AUTORISEES
        else None
    )


def normaliser_nature_comptable(valeur: object | None) -> str | None:
    """Normalisation historique utilisée par le moteur ACHAT."""
    normalisee = _normaliser_texte(valeur)

    if not normalisee:
        return None

    nature = _ALIASES_ACHAT.get(normalisee, normalisee)

    if nature not in REGLES_ACHAT:
        return None

    return nature


def normaliser_nature_vente(valeur: object | None) -> str | None:
    """Retourne uniquement une nature reconnue par le moteur VENTE."""
    normalisee = _normaliser_texte(valeur)

    if not normalisee:
        return None

    nature = _ALIASES_VENTE.get(normalisee, normalisee)

    if nature not in REGLES_VENTE:
        return None

    return nature


def obtenir_regle_achat(valeur: object | None) -> RegleCompteHT | None:
    nature = normaliser_nature_comptable(valeur)

    if nature is None:
        return None

    return REGLES_ACHAT[nature]


def obtenir_regle_vente(valeur: object | None) -> RegleCompteVente | None:
    nature = normaliser_nature_vente(valeur)

    if nature is None:
        return None

    return REGLES_VENTE[nature]


def compte_correspond_a_famille(
    compte: object | None,
    famille_cgnc: str,
) -> bool:
    """Vérifie qu'un numéro de compte appartient à la famille attendue."""
    if compte is None:
        return False

    propre = "".join(
        caractere
        for caractere in str(compte).strip()
        if caractere.isdigit()
    )

    return bool(propre) and propre.startswith(famille_cgnc)


# ============================================================
# TVA ACHAT
# ============================================================

FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS = "34551"
FAMILLE_TVA_RECUPERABLE_CHARGES = "34552"


def normaliser_traitement_comptable_confirme(
    valeur: object | None,
) -> Literal["charge", "immobilisation"] | None:
    """Normalise uniquement une décision comptable explicitement confirmée."""
    normalisee = _normaliser_texte(valeur)

    mapping = {
        "charge": "charge",
        "charges": "charge",
        "immobilisation": "immobilisation",
        "immobilise": "immobilisation",
        "immobilisee": "immobilisation",
        "immobilisees": "immobilisation",
    }

    return mapping.get(normalisee)


def obtenir_famille_tva_achat(
    traitement_suggere: object | None,
    traitement_confirme: object | None = None,
) -> str | None:
    """Détermine la famille de TVA récupérable pour un ACHAT."""
    confirme = normaliser_traitement_comptable_confirme(
        traitement_confirme
    )

    if confirme == "charge":
        return FAMILLE_TVA_RECUPERABLE_CHARGES

    if confirme == "immobilisation":
        return FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS

    suggere = _normaliser_texte(traitement_suggere)

    if suggere == "charge":
        return FAMILLE_TVA_RECUPERABLE_CHARGES

    return None


# ============================================================
# TVA VENTE
# ============================================================

# Etat - TVA facturée. Le compte Topaze exact de l'entreprise est résolu
# dans le plan comptable ; cette constante reste uniquement une famille.
FAMILLE_TVA_FACTUREE = "4455"


def obtenir_famille_tva_vente() -> str:
    """Famille CGNC de la TVA facturée / collectée sur une vente."""
    return FAMILLE_TVA_FACTUREE
