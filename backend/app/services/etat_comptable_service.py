"""Controles locaux communs aux etats CPC/Bilan V2.

Ce module ne produit aucun ajustement et n'ecrit jamais en base. Il compare
deux lectures deterministes des memes lignes validees : Grand Livre brut et
agregation Balance par compte.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass(slots=True)
class ControleGrandLivreBalance:
    total_debit_grand_livre: Decimal
    total_credit_grand_livre: Decimal
    total_debit_balance: Decimal
    total_credit_balance: Decimal
    coherent: bool
    groupes_sources_desequilibres: int = 0


@dataclass(slots=True)
class LignesControlees:
    lignes: list[object]
    anomalies: list[str]
    controle: ControleGrandLivreBalance


def decimal_exploitable(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not result.is_finite():
        return None
    return result.quantize(MONEY)


def _ajouter_unique(anomalies: list[str], message: str) -> None:
    if message not in anomalies:
        anomalies.append(message)


def controler_lignes_validees(
    lignes: Iterable[object],
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
) -> LignesControlees:
    """Filtre et controle les lignes avant calcul d'un etat.

    Une ligne hors tenant ou hors periode n'est jamais incorporee au calcul.
    Les attributs de portee/source peuvent manquer dans les tests unitaires,
    mais ils sont obligatoires sur le modele SQLAlchemy reel.
    """
    retenues: list[object] = []
    anomalies: list[str] = []
    sources: dict[tuple[str, object], list[Decimal]] = {}

    for index, ligne in enumerate(lignes, start=1):
        ligne_cabinet = getattr(ligne, "cabinet_id", cabinet_id)
        ligne_entreprise = getattr(ligne, "entreprise_id", entreprise_id)
        if ligne_cabinet != cabinet_id or ligne_entreprise != entreprise_id:
            _ajouter_unique(anomalies, "Une ligne hors cabinet ou entreprise a ete exclue de l'etat.")
            continue

        ligne_date = getattr(ligne, "date_ecriture", None)
        if ligne_date is not None and (
            (date_debut is not None and ligne_date < date_debut)
            or (date_fin is not None and ligne_date > date_fin)
        ):
            _ajouter_unique(anomalies, "Une ligne presente un exercice incoherent et a ete exclue de l'etat.")
            continue

        compte = getattr(ligne, "compte", None)
        if compte is None or not str(compte).strip():
            _ajouter_unique(anomalies, "Une ligne validee ne contient aucun numero de compte.")
            continue

        debit = decimal_exploitable(getattr(ligne, "debit", None))
        credit = decimal_exploitable(getattr(ligne, "credit", None))
        if debit is None or credit is None or debit < ZERO or credit < ZERO:
            _ajouter_unique(anomalies, f"Montant non exploitable sur la ligne {index} du compte {compte}.")
            continue
        if not ((debit > ZERO and credit == ZERO) or (credit > ZERO and debit == ZERO)):
            _ajouter_unique(anomalies, f"Sens Debit/Credit invalide sur la ligne {index} du compte {compte}.")
            continue

        retenues.append(ligne)
        source_values = (
            ("ecriture", getattr(ligne, "ecriture_id", None)),
            ("banque", getattr(ligne, "mouvement_bancaire_id", None)),
            ("cloture", getattr(ligne, "regularisation_cloture_id", None)),
        )
        sources_presentes = [(kind, value) for kind, value in source_values if value is not None]
        if len(sources_presentes) == 1:
            bucket = sources.setdefault(sources_presentes[0], [ZERO, ZERO])
            bucket[0] += debit
            bucket[1] += credit
        elif any(hasattr(ligne, name) for name in ("ecriture_id", "mouvement_bancaire_id", "regularisation_cloture_id")):
            _ajouter_unique(anomalies, f"Source comptable absente ou ambigue sur la ligne {index}.")

    groupes_desequilibres = 0
    for (kind, source_id), (debit, credit) in sources.items():
        if abs(debit - credit) > MONEY:
            groupes_desequilibres += 1
            _ajouter_unique(
                anomalies,
                f"Lignes non equilibrees pour la source validee {kind} {source_id}: {debit} != {credit}.",
            )

    total_debit_gl = sum((decimal_exploitable(getattr(line, "debit", None)) or ZERO for line in retenues), ZERO)
    total_credit_gl = sum((decimal_exploitable(getattr(line, "credit", None)) or ZERO for line in retenues), ZERO)
    balance: dict[str, list[Decimal]] = {}
    for line in retenues:
        compte = str(getattr(line, "compte"))
        bucket = balance.setdefault(compte, [ZERO, ZERO])
        bucket[0] += decimal_exploitable(getattr(line, "debit", None)) or ZERO
        bucket[1] += decimal_exploitable(getattr(line, "credit", None)) or ZERO
    total_debit_balance = sum((values[0] for values in balance.values()), ZERO)
    total_credit_balance = sum((values[1] for values in balance.values()), ZERO)
    coherent = (
        abs(total_debit_gl - total_debit_balance) <= MONEY
        and abs(total_credit_gl - total_credit_balance) <= MONEY
    )
    if not coherent:
        _ajouter_unique(anomalies, "Les totaux Grand Livre et Balance ne correspondent pas.")

    return LignesControlees(
        lignes=retenues,
        anomalies=anomalies,
        controle=ControleGrandLivreBalance(
            total_debit_grand_livre=total_debit_gl.quantize(MONEY),
            total_credit_grand_livre=total_credit_gl.quantize(MONEY),
            total_debit_balance=total_debit_balance.quantize(MONEY),
            total_credit_balance=total_credit_balance.quantize(MONEY),
            coherent=coherent,
            groupes_sources_desequilibres=groupes_desequilibres,
        ),
    )
