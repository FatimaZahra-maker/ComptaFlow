"""Construction du Compte de Produits et Charges depuis le Grand Livre.

Cette V1 calcule le CPC uniquement à partir des lignes comptables VALIDÉES
et exprimées en MAD.

Règles CGNC utilisées :
- 61 : charges d'exploitation ;
- 63 : charges financières ;
- 65 : charges non courantes ;
- 67 : impôts sur les résultats ;
- 71 : produits d'exploitation ;
- 73 : produits financiers ;
- 75 : produits non courants.

Une ligne de classe 6 ou 7 ne correspondant pas à une rubrique reconnue
n'est jamais rangée arbitrairement : le CPC est marqué « à vérifier ».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.ligne_comptable import LigneComptable
from app.services.etat_comptable_service import ControleGrandLivreBalance, controler_lignes_validees

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

RUBRIQUE_CHARGES_EXPLOITATION = "charges_exploitation"
RUBRIQUE_CHARGES_FINANCIERES = "charges_financieres"
RUBRIQUE_CHARGES_NON_COURANTES = "charges_non_courantes"
RUBRIQUE_IMPOTS_RESULTATS = "impots_sur_resultats"
RUBRIQUE_PRODUITS_EXPLOITATION = "produits_exploitation"
RUBRIQUE_PRODUITS_FINANCIERS = "produits_financiers"
RUBRIQUE_PRODUITS_NON_COURANTS = "produits_non_courants"
RUBRIQUE_NON_CLASSEE = "non_classee"

RUBRIQUES_CHARGES = {
    RUBRIQUE_CHARGES_EXPLOITATION,
    RUBRIQUE_CHARGES_FINANCIERES,
    RUBRIQUE_CHARGES_NON_COURANTES,
    RUBRIQUE_IMPOTS_RESULTATS,
}
RUBRIQUES_PRODUITS = {
    RUBRIQUE_PRODUITS_EXPLOITATION,
    RUBRIQUE_PRODUITS_FINANCIERS,
    RUBRIQUE_PRODUITS_NON_COURANTS,
}


@dataclass(slots=True)
class CpcCompteDetail:
    compte: str
    libelle_compte: str | None
    rubrique: str
    debit: Decimal
    credit: Decimal
    montant: Decimal


@dataclass(slots=True)
class CpcResultat:
    entreprise_id: uuid.UUID
    annee: int
    date_debut: date
    date_fin: date

    produits_exploitation: Decimal = ZERO
    charges_exploitation: Decimal = ZERO
    resultat_exploitation: Decimal = ZERO

    produits_financiers: Decimal = ZERO
    charges_financieres: Decimal = ZERO
    resultat_financier: Decimal = ZERO

    resultat_courant: Decimal = ZERO

    produits_non_courants: Decimal = ZERO
    charges_non_courantes: Decimal = ZERO
    resultat_non_courant: Decimal = ZERO

    resultat_avant_impots: Decimal = ZERO
    impots_sur_resultats: Decimal = ZERO
    resultat_net: Decimal = ZERO

    nombre_lignes: int = 0
    nombre_comptes: int = 0
    a_verifier: bool = False
    raisons_verification: list[str] = field(default_factory=list)
    comptes: list[CpcCompteDetail] = field(default_factory=list)
    source_calcul: str = "grand_livre_valide_mad"


def _money(value: object | None) -> Decimal:
    if value is None or value == "":
        return ZERO
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def normaliser_compte(value: object | None) -> str:
    if value is None:
        return ""
    return "".join(character for character in str(value).strip() if character.isdigit())


def determiner_rubrique_cpc(compte: object | None) -> str | None:
    """Retourne la rubrique CPC reconnue à partir du préfixe CGNC."""
    numero = normaliser_compte(compte)
    if not numero:
        return None

    mapping = (
        ("61", RUBRIQUE_CHARGES_EXPLOITATION),
        ("63", RUBRIQUE_CHARGES_FINANCIERES),
        ("65", RUBRIQUE_CHARGES_NON_COURANTES),
        ("67", RUBRIQUE_IMPOTS_RESULTATS),
        ("71", RUBRIQUE_PRODUITS_EXPLOITATION),
        ("73", RUBRIQUE_PRODUITS_FINANCIERS),
        ("75", RUBRIQUE_PRODUITS_NON_COURANTS),
    )
    for prefix, rubrique in mapping:
        if numero.startswith(prefix):
            return rubrique
    return None


def _montant_rubrique(rubrique: str, debit: Decimal, credit: Decimal) -> Decimal:
    if rubrique in RUBRIQUES_CHARGES:
        return (debit - credit).quantize(MONEY)
    if rubrique in RUBRIQUES_PRODUITS:
        return (credit - debit).quantize(MONEY)
    return ZERO


def calculer_cpc_depuis_lignes(
    *,
    entreprise_id: uuid.UUID,
    annee: int,
    lignes: Iterable[object],
    libelles_comptes: dict[str, str] | None = None,
) -> CpcResultat:
    """Calcule le CPC à partir d'objets ayant compte/debit/credit."""
    date_debut = date(annee, 1, 1)
    date_fin = date(annee, 12, 31)
    libelles = libelles_comptes or {}

    agregats: dict[str, dict[str, object]] = {}
    raisons: list[str] = []
    nombre_lignes = 0

    for ligne in lignes:
        nombre_lignes += 1
        compte = normaliser_compte(getattr(ligne, "compte", None))
        debit = _money(getattr(ligne, "debit", None))
        credit = _money(getattr(ligne, "credit", None))

        if not compte:
            message = "Une ligne validée ne contient aucun numéro de compte."
            if message not in raisons:
                raisons.append(message)
            continue

        # Le CPC ne concerne que les classes 6 et 7.
        if not (compte.startswith("6") or compte.startswith("7")):
            continue

        rubrique = determiner_rubrique_cpc(compte)
        if rubrique is None:
            message = (
                f"Compte {compte} de classe {compte[0]} non reconnu par le moteur CPC V1 : "
                "classement manuel requis."
            )
            if message not in raisons:
                raisons.append(message)
            rubrique = RUBRIQUE_NON_CLASSEE

        current = agregats.setdefault(
            compte,
            {
                "rubrique": rubrique,
                "debit": ZERO,
                "credit": ZERO,
            },
        )
        current["debit"] = _money(current["debit"]) + debit
        current["credit"] = _money(current["credit"]) + credit

    details: list[CpcCompteDetail] = []
    totals: dict[str, Decimal] = {
        RUBRIQUE_CHARGES_EXPLOITATION: ZERO,
        RUBRIQUE_CHARGES_FINANCIERES: ZERO,
        RUBRIQUE_CHARGES_NON_COURANTES: ZERO,
        RUBRIQUE_IMPOTS_RESULTATS: ZERO,
        RUBRIQUE_PRODUITS_EXPLOITATION: ZERO,
        RUBRIQUE_PRODUITS_FINANCIERS: ZERO,
        RUBRIQUE_PRODUITS_NON_COURANTS: ZERO,
    }

    for compte in sorted(agregats):
        row = agregats[compte]
        rubrique = str(row["rubrique"])
        debit = _money(row["debit"])
        credit = _money(row["credit"])
        montant = _montant_rubrique(rubrique, debit, credit)

        if rubrique in totals:
            totals[rubrique] = (totals[rubrique] + montant).quantize(MONEY)

        details.append(
            CpcCompteDetail(
                compte=compte,
                libelle_compte=libelles.get(compte),
                rubrique=rubrique,
                debit=debit,
                credit=credit,
                montant=montant,
            )
        )

    produits_exploitation = totals[RUBRIQUE_PRODUITS_EXPLOITATION]
    charges_exploitation = totals[RUBRIQUE_CHARGES_EXPLOITATION]
    resultat_exploitation = (produits_exploitation - charges_exploitation).quantize(MONEY)

    produits_financiers = totals[RUBRIQUE_PRODUITS_FINANCIERS]
    charges_financieres = totals[RUBRIQUE_CHARGES_FINANCIERES]
    resultat_financier = (produits_financiers - charges_financieres).quantize(MONEY)

    resultat_courant = (resultat_exploitation + resultat_financier).quantize(MONEY)

    produits_non_courants = totals[RUBRIQUE_PRODUITS_NON_COURANTS]
    charges_non_courantes = totals[RUBRIQUE_CHARGES_NON_COURANTES]
    resultat_non_courant = (produits_non_courants - charges_non_courantes).quantize(MONEY)

    resultat_avant_impots = (resultat_courant + resultat_non_courant).quantize(MONEY)
    impots_sur_resultats = totals[RUBRIQUE_IMPOTS_RESULTATS]
    resultat_net = (resultat_avant_impots - impots_sur_resultats).quantize(MONEY)

    return CpcResultat(
        entreprise_id=entreprise_id,
        annee=annee,
        date_debut=date_debut,
        date_fin=date_fin,
        produits_exploitation=produits_exploitation,
        charges_exploitation=charges_exploitation,
        resultat_exploitation=resultat_exploitation,
        produits_financiers=produits_financiers,
        charges_financieres=charges_financieres,
        resultat_financier=resultat_financier,
        resultat_courant=resultat_courant,
        produits_non_courants=produits_non_courants,
        charges_non_courantes=charges_non_courantes,
        resultat_non_courant=resultat_non_courant,
        resultat_avant_impots=resultat_avant_impots,
        impots_sur_resultats=impots_sur_resultats,
        resultat_net=resultat_net,
        nombre_lignes=nombre_lignes,
        nombre_comptes=len(details),
        a_verifier=bool(raisons),
        raisons_verification=raisons,
        comptes=details,
    )


def calculer_cpc(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    annee: int,
) -> CpcResultat:
    date_debut = date(annee, 1, 1)
    date_fin = date(annee, 12, 31)

    lignes = db.execute(
        select(LigneComptable)
        .where(
            LigneComptable.cabinet_id == cabinet_id,
            LigneComptable.entreprise_id == entreprise_id,
            LigneComptable.est_validee.is_(True),
            LigneComptable.date_ecriture >= date_debut,
            LigneComptable.date_ecriture <= date_fin,
        )
        .order_by(LigneComptable.compte, LigneComptable.date_ecriture)
    ).scalars().all()

    comptes_plan = db.execute(
        select(CompteComptableEntreprise).where(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
        )
    ).scalars().all()

    libelles = {
        normaliser_compte(compte.numero_compte): compte.libelle
        for compte in comptes_plan
        if normaliser_compte(compte.numero_compte)
    }

    return calculer_cpc_depuis_lignes(
        entreprise_id=entreprise_id,
        annee=annee,
        lignes=lignes,
        libelles_comptes=libelles,
    )


# CPC V2 conserve le calcul V1 ci-dessus et ajoute comparaison, tracabilite
# des comptes non classes et controles du chemin Grand Livre -> Balance.
LIBELLES_RUBRIQUES_V2 = {
    RUBRIQUE_PRODUITS_EXPLOITATION: "Produits d'exploitation",
    RUBRIQUE_CHARGES_EXPLOITATION: "Charges d'exploitation",
    RUBRIQUE_PRODUITS_FINANCIERS: "Produits financiers",
    RUBRIQUE_CHARGES_FINANCIERES: "Charges financieres",
    RUBRIQUE_PRODUITS_NON_COURANTS: "Produits non courants",
    RUBRIQUE_CHARGES_NON_COURANTES: "Charges non courantes",
    RUBRIQUE_IMPOTS_RESULTATS: "Impots sur les resultats",
}
LIBELLES_RESULTATS_V2 = {
    "resultat_exploitation": "Resultat d'exploitation",
    "resultat_financier": "Resultat financier",
    "resultat_courant": "Resultat courant",
    "resultat_non_courant": "Resultat non courant",
    "resultat_avant_impots": "Resultat avant impots",
    "resultat_net": "Resultat net",
}


@dataclass(slots=True)
class CpcComparaison:
    code: str
    libelle: str
    montant_n: Decimal
    montant_n_1: Decimal | None
    variation_mad: Decimal | None
    variation_pct: Decimal | None


@dataclass(slots=True)
class CpcV2Resultat:
    entreprise_id: uuid.UUID
    exercice: int
    exercice_precedent: int
    donnees_n_1_disponibles: bool
    rubriques: list[CpcComparaison]
    resultats: list[CpcComparaison]
    comptes: list[CpcCompteDetail]
    comptes_non_classes: list[CpcCompteDetail]
    anomalies: list[str]
    statut: str
    controle_grand_livre_balance: ControleGrandLivreBalance
    nombre_lignes: int
    nombre_comptes: int
    source_calcul: str = "lignes_validees_grand_livre_balance"


def _comparaison(
    code: str,
    libelle: str,
    montant_n: Decimal,
    montant_n_1: Decimal | None,
) -> CpcComparaison:
    if montant_n_1 is None:
        return CpcComparaison(code, libelle, montant_n, None, None, None)
    variation = (montant_n - montant_n_1).quantize(MONEY)
    variation_pct = None
    if montant_n_1 != ZERO:
        variation_pct = ((variation / abs(montant_n_1)) * Decimal("100")).quantize(MONEY)
    return CpcComparaison(code, libelle, montant_n, montant_n_1, variation, variation_pct)


def calculer_cpc_v2_depuis_lignes(
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    exercice: int,
    lignes_n: Iterable[object],
    lignes_n_1: Iterable[object] = (),
    libelles_comptes: dict[str, str] | None = None,
) -> CpcV2Resultat:
    controle_n = controler_lignes_validees(
        lignes_n, cabinet_id=cabinet_id, entreprise_id=entreprise_id,
        date_debut=date(exercice, 1, 1), date_fin=date(exercice, 12, 31),
    )
    controle_n_1 = controler_lignes_validees(
        lignes_n_1, cabinet_id=cabinet_id, entreprise_id=entreprise_id,
        date_debut=date(exercice - 1, 1, 1), date_fin=date(exercice - 1, 12, 31),
    )
    current = calculer_cpc_depuis_lignes(
        entreprise_id=entreprise_id, annee=exercice, lignes=controle_n.lignes,
        libelles_comptes=libelles_comptes,
    )
    previous = calculer_cpc_depuis_lignes(
        entreprise_id=entreprise_id, annee=exercice - 1, lignes=controle_n_1.lignes,
        libelles_comptes=libelles_comptes,
    )
    previous_available = any(
        normaliser_compte(getattr(line, "compte", None)).startswith(("6", "7"))
        for line in controle_n_1.lignes
    )
    anomalies = list(controle_n.anomalies)
    anomalies.extend(reason for reason in current.raisons_verification if reason not in anomalies)
    for reason in controle_n_1.anomalies + previous.raisons_verification:
        message = f"Exercice N-1: {reason}"
        if message not in anomalies:
            anomalies.append(message)

    rubriques = [
        _comparaison(
            code, label, getattr(current, code),
            getattr(previous, code) if previous_available else None,
        )
        for code, label in LIBELLES_RUBRIQUES_V2.items()
    ]
    resultats = [
        _comparaison(
            code, label, getattr(current, code),
            getattr(previous, code) if previous_available else None,
        )
        for code, label in LIBELLES_RESULTATS_V2.items()
    ]
    non_classes = [item for item in current.comptes if item.rubrique == RUBRIQUE_NON_CLASSEE]
    return CpcV2Resultat(
        entreprise_id=entreprise_id,
        exercice=exercice,
        exercice_precedent=exercice - 1,
        donnees_n_1_disponibles=previous_available,
        rubriques=rubriques,
        resultats=resultats,
        comptes=current.comptes,
        comptes_non_classes=non_classes,
        anomalies=anomalies,
        statut="a_verifier" if anomalies else "ok",
        controle_grand_livre_balance=controle_n.controle,
        nombre_lignes=current.nombre_lignes,
        nombre_comptes=current.nombre_comptes,
    )


def calculer_cpc_v2(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    exercice: int,
) -> CpcV2Resultat:
    lignes = db.execute(select(LigneComptable).where(
        LigneComptable.cabinet_id == cabinet_id,
        LigneComptable.entreprise_id == entreprise_id,
        LigneComptable.est_validee.is_(True),
        LigneComptable.date_ecriture >= date(exercice - 1, 1, 1),
        LigneComptable.date_ecriture <= date(exercice, 12, 31),
    ).order_by(LigneComptable.date_ecriture, LigneComptable.compte)).scalars().all()
    comptes_plan = db.execute(select(CompteComptableEntreprise).where(
        CompteComptableEntreprise.cabinet_id == cabinet_id,
        CompteComptableEntreprise.entreprise_id == entreprise_id,
        CompteComptableEntreprise.is_active.is_(True),
    )).scalars().all()
    labels = {
        normaliser_compte(compte.numero_compte): compte.libelle
        for compte in comptes_plan if normaliser_compte(compte.numero_compte)
    }
    return calculer_cpc_v2_depuis_lignes(
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        exercice=exercice,
        lignes_n=[line for line in lignes if line.date_ecriture.year == exercice],
        lignes_n_1=[line for line in lignes if line.date_ecriture.year == exercice - 1],
        libelles_comptes=labels,
    )
