"""Synthèse TVA comptable basée sur les lignes Débit / Crédit validées.

Cette V1 calcule une vue comptable de la TVA à partir du Grand Livre :
- TVA facturée / collectée : famille 4455...
- TVA récupérable sur immobilisations : famille 34551...
- TVA récupérable sur charges : famille 34552...

Elle ne constitue pas une déclaration fiscale prête à déposer. Les retenues à
la source TVA, reports de crédit, prorata, régularisations et cas fiscaux
spécifiques restent volontairement hors de cette V1.
"""
from __future__ import annotations

from collections import defaultdict
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.ecriture import EcritureComptable
from app.models.enums import StatutValidationEnum, TypeEcritureEnum
from app.models.ligne_comptable import LigneComptable
from app.models.tva_periode import (
    TvaConfigurationEntreprise,
    TvaCreditUtilisation,
    TvaPeriode,
    TvaRegularisation,
)

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

FAMILLE_TVA_COLLECTEE = "4455"
FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS = "34551"
FAMILLE_TVA_RECUPERABLE_CHARGES = "34552"

NATURE_COLLECTEE = "collectee"
NATURE_DEDUCTIBLE_IMMOBILISATIONS = "deductible_immobilisations"
NATURE_DEDUCTIBLE_CHARGES = "deductible_charges"

LIMITES_DECLARATION = [
    "Retenue à la source TVA non intégrée dans cette V1.",
    "Report de crédit TVA d'une période antérieure non appliqué automatiquement.",
    "Prorata de déduction et régularisations fiscales non calculés automatiquement.",
    "La synthèse doit être validée par le comptable avant toute déclaration fiscale.",
]


@dataclass(slots=True)
class TvaCompteDetail:
    compte: str
    nature: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    montant_net: Decimal = ZERO


@dataclass(slots=True)
class TvaMoisResultat:
    mois: int
    annee: int
    tva_collectee: Decimal = ZERO
    tva_deductible_charges: Decimal = ZERO
    tva_deductible_immobilisations: Decimal = ZERO
    tva_deductible: Decimal = ZERO
    tva_nette: Decimal = ZERO
    tva_a_payer: Decimal = ZERO
    credit_tva: Decimal = ZERO
    nombre_ecritures: int = 0
    nombre_lignes_tva: int = 0
    a_verifier: bool = False
    raisons_verification: list[str] = field(default_factory=list)
    comptes: list[TvaCompteDetail] = field(default_factory=list)


@dataclass(slots=True)
class TvaAnneeResultat:
    entreprise_id: uuid.UUID
    annee: int
    mensualites: list[TvaMoisResultat]
    total_tva_collectee: Decimal
    total_tva_deductible_charges: Decimal
    total_tva_deductible_immobilisations: Decimal
    total_tva_deductible: Decimal
    total_tva_nette: Decimal
    total_tva_a_payer_technique: Decimal
    total_credit_tva_technique: Decimal
    nombre_mois_a_verifier: int
    source_calcul: str = "lignes_comptables_validees"
    declaration_fiscale_prete: bool = False
    limites: list[str] = field(default_factory=lambda: list(LIMITES_DECLARATION))


def _money(value: object | None) -> Decimal:
    if value is None or value == "":
        return ZERO
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def _digits(compte: object | None) -> str:
    if compte is None:
        return ""
    return "".join(char for char in str(compte).strip() if char.isdigit())


def classifier_compte_tva(compte: object | None) -> str | None:
    """Classe un compte TVA par famille sans inventer de numéro complet."""
    propre = _digits(compte)
    if propre.startswith(FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS):
        return NATURE_DEDUCTIBLE_IMMOBILISATIONS
    if propre.startswith(FAMILLE_TVA_RECUPERABLE_CHARGES):
        return NATURE_DEDUCTIBLE_CHARGES
    if propre.startswith(FAMILLE_TVA_COLLECTEE):
        return NATURE_COLLECTEE
    return None


def _type_value(value: object | None) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "")


def _mois_de_date(value: object | None, annee: int) -> int | None:
    if not isinstance(value, date):
        return None
    if value.year != annee:
        return None
    return value.month


def _ajouter_raison(mois: TvaMoisResultat, message: str) -> None:
    if message and message not in mois.raisons_verification:
        mois.raisons_verification.append(message)
    mois.a_verifier = True


def _compte_net(nature: str, debit: Decimal, credit: Decimal) -> Decimal:
    if nature == NATURE_COLLECTEE:
        return (credit - debit).quantize(MONEY)
    return (debit - credit).quantize(MONEY)


def construire_synthese_tva(
    *,
    entreprise_id: uuid.UUID,
    annee: int,
    lignes: list[object],
    ecritures: list[object],
) -> TvaAnneeResultat:
    """Construit la synthèse annuelle depuis des objets ligne/écriture.

    La fonction est pure côté calcul afin d'être testable sans PostgreSQL.
    """
    mensualites = {
        number: TvaMoisResultat(mois=number, annee=annee)
        for number in range(1, 13)
    }

    lignes_par_ecriture: dict[object, list[object]] = defaultdict(list)
    comptes_par_mois: dict[int, dict[tuple[str, str], dict[str, Decimal]]] = defaultdict(dict)
    ligne_ids_vus: set[object] = set()

    for ligne in lignes:
        mois_numero = _mois_de_date(getattr(ligne, "date_ecriture", None), annee)
        if mois_numero is None:
            continue

        nature = classifier_compte_tva(getattr(ligne, "compte", None))
        if nature is None:
            continue

        ligne_id = getattr(ligne, "id", None)
        if ligne_id is not None:
            if ligne_id in ligne_ids_vus:
                _ajouter_raison(
                    mensualites[mois_numero],
                    "Une ligne TVA est présente plusieurs fois dans la période.",
                )
                continue
            ligne_ids_vus.add(ligne_id)
        if hasattr(ligne, "entreprise_id") and getattr(ligne, "entreprise_id", None) is None:
            _ajouter_raison(
                mensualites[mois_numero],
                "Une ligne TVA ne porte aucune entreprise.",
            )

        debit = _money(getattr(ligne, "debit", None))
        credit = _money(getattr(ligne, "credit", None))
        net = _compte_net(nature, debit, credit)
        mois = mensualites[mois_numero]
        mois.nombre_lignes_tva += 1

        if nature == NATURE_COLLECTEE:
            mois.tva_collectee += net
        elif nature == NATURE_DEDUCTIBLE_CHARGES:
            mois.tva_deductible_charges += net
        elif nature == NATURE_DEDUCTIBLE_IMMOBILISATIONS:
            mois.tva_deductible_immobilisations += net

        compte = _digits(getattr(ligne, "compte", None)) or str(getattr(ligne, "compte", ""))
        key = (compte, nature)
        bucket = comptes_par_mois[mois_numero].setdefault(
            key,
            {"debit": ZERO, "credit": ZERO, "net": ZERO},
        )
        bucket["debit"] += debit
        bucket["credit"] += credit
        bucket["net"] += net

        ecriture_id = getattr(ligne, "ecriture_id", None)
        if ecriture_id is not None:
            lignes_par_ecriture[ecriture_id].append(ligne)

    # Contrôle pièce par pièce : une écriture validée avec TVA positive doit
    # avoir une ligne TVA compatible et du même montant comptable en MAD.
    for ecriture in ecritures:
        mois_numero = _mois_de_date(getattr(ecriture, "date_piece", None), annee)
        if mois_numero is None:
            continue

        mois = mensualites[mois_numero]
        type_ecriture = _type_value(getattr(ecriture, "type_ecriture", None))
        if type_ecriture not in {TypeEcritureEnum.ACHAT.value, TypeEcritureEnum.VENTE.value}:
            continue

        mois.nombre_ecritures += 1
        montant_tva = _money(getattr(ecriture, "montant_tva", None))
        if montant_tva <= ZERO:
            continue

        compte_tva = getattr(ecriture, "compte_tva", None)
        nature_attendue = classifier_compte_tva(compte_tva)

        if type_ecriture == TypeEcritureEnum.ACHAT.value:
            if nature_attendue not in {
                NATURE_DEDUCTIBLE_CHARGES,
                NATURE_DEDUCTIBLE_IMMOBILISATIONS,
            }:
                _ajouter_raison(
                    mois,
                    "Au moins une facture d'achat validée avec TVA positive utilise "
                    "un compte TVA hors familles 34551/34552 ou sans compte TVA.",
                )
        else:
            if nature_attendue != NATURE_COLLECTEE:
                _ajouter_raison(
                    mois,
                    "Au moins une facture de vente validée avec TVA positive utilise "
                    "un compte TVA hors famille 4455 ou sans compte TVA.",
                )

        candidates = [
            line
            for line in lignes_par_ecriture.get(getattr(ecriture, "id", None), [])
            if classifier_compte_tva(getattr(line, "compte", None)) is not None
        ]
        if not candidates:
            _ajouter_raison(
                mois,
                "Au moins une facture validée avec TVA positive n'a aucune ligne TVA "
                "validée dans le Grand Livre.",
            )
            continue

        if any(
            _mois_de_date(getattr(line, "date_ecriture", None), annee) != mois_numero
            for line in candidates
        ):
            _ajouter_raison(
                mois,
                "La période d'au moins une ligne TVA diffère de celle de sa facture.",
            )

        if type_ecriture == TypeEcritureEnum.ACHAT.value:
            ligne_tva = sum(
                (
                    _money(getattr(line, "debit", None))
                    - _money(getattr(line, "credit", None))
                    for line in candidates
                    if classifier_compte_tva(getattr(line, "compte", None))
                    in {NATURE_DEDUCTIBLE_CHARGES, NATURE_DEDUCTIBLE_IMMOBILISATIONS}
                ),
                ZERO,
            )
        else:
            ligne_tva = sum(
                (
                    _money(getattr(line, "credit", None))
                    - _money(getattr(line, "debit", None))
                    for line in candidates
                    if classifier_compte_tva(getattr(line, "compte", None)) == NATURE_COLLECTEE
                ),
                ZERO,
            )

        ligne_tva = ligne_tva.quantize(MONEY)
        if abs(ligne_tva - montant_tva) > MONEY:
            _ajouter_raison(
                mois,
                "Au moins une facture présente un écart entre le montant TVA de "
                "l'écriture et sa ligne TVA du Grand Livre.",
            )

    for numero, mois in mensualites.items():
        mois.tva_collectee = mois.tva_collectee.quantize(MONEY)
        mois.tva_deductible_charges = mois.tva_deductible_charges.quantize(MONEY)
        mois.tva_deductible_immobilisations = (
            mois.tva_deductible_immobilisations.quantize(MONEY)
        )
        mois.tva_deductible = (
            mois.tva_deductible_charges + mois.tva_deductible_immobilisations
        ).quantize(MONEY)
        mois.tva_nette = (mois.tva_collectee - mois.tva_deductible).quantize(MONEY)
        mois.tva_a_payer = max(mois.tva_nette, ZERO).quantize(MONEY)
        mois.credit_tva = max(-mois.tva_nette, ZERO).quantize(MONEY)

        details: list[TvaCompteDetail] = []
        for (compte, nature), values in sorted(comptes_par_mois[numero].items()):
            details.append(
                TvaCompteDetail(
                    compte=compte,
                    nature=nature,
                    debit=values["debit"].quantize(MONEY),
                    credit=values["credit"].quantize(MONEY),
                    montant_net=values["net"].quantize(MONEY),
                )
            )
        mois.comptes = details

    ordered = [mensualites[number] for number in range(1, 13)]

    total_collectee = sum((m.tva_collectee for m in ordered), ZERO).quantize(MONEY)
    total_charges = sum((m.tva_deductible_charges for m in ordered), ZERO).quantize(MONEY)
    total_immo = sum(
        (m.tva_deductible_immobilisations for m in ordered), ZERO
    ).quantize(MONEY)
    total_deductible = (total_charges + total_immo).quantize(MONEY)
    total_nette = (total_collectee - total_deductible).quantize(MONEY)

    return TvaAnneeResultat(
        entreprise_id=entreprise_id,
        annee=annee,
        mensualites=ordered,
        total_tva_collectee=total_collectee,
        total_tva_deductible_charges=total_charges,
        total_tva_deductible_immobilisations=total_immo,
        total_tva_deductible=total_deductible,
        total_tva_nette=total_nette,
        total_tva_a_payer_technique=sum(
            (m.tva_a_payer for m in ordered), ZERO
        ).quantize(MONEY),
        total_credit_tva_technique=sum(
            (m.credit_tva for m in ordered), ZERO
        ).quantize(MONEY),
        nombre_mois_a_verifier=sum(1 for m in ordered if m.a_verifier),
    )


def calculer_tva_annuelle(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    annee: int,
) -> TvaAnneeResultat:
    """Lit PostgreSQL puis construit la synthèse TVA comptable annuelle."""
    debut = date(annee, 1, 1)
    fin = date(annee + 1, 1, 1)

    lignes = db.execute(
        select(LigneComptable).where(
            LigneComptable.cabinet_id == cabinet_id,
            LigneComptable.entreprise_id == entreprise_id,
            LigneComptable.est_validee.is_(True),
            LigneComptable.tva_periode_id.is_(None),
            LigneComptable.date_ecriture >= debut,
            LigneComptable.date_ecriture < fin,
        )
    ).scalars().all()

    ecritures = db.execute(
        select(EcritureComptable).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation.in_([
                StatutValidationEnum.PRETE_TOPAZE,
                StatutValidationEnum.SAISIE_TOPAZE,
                StatutValidationEnum.VALIDE,
            ]),
            EcritureComptable.date_piece >= debut,
            EcritureComptable.date_piece < fin,
            EcritureComptable.type_ecriture.in_(
                [TypeEcritureEnum.ACHAT, TypeEcritureEnum.VENTE]
            ),
        )
    ).scalars().all()

    return construire_synthese_tva(
        entreprise_id=entreprise_id,
        annee=annee,
        lignes=list(lignes),
        ecritures=list(ecritures),
    )


# ============================================================
# TVA V2 — PÉRIODES, REPORTS ET RÉGULARISATIONS
# ============================================================


@dataclass(slots=True)
class TvaPeriodeCalcul:
    tva_collectee: Decimal
    tva_recuperable_charges: Decimal
    tva_recuperable_immobilisations: Decimal
    credit_anterieur: Decimal
    regularisations: Decimal
    retenues_tva: Decimal
    tva_nette: Decimal
    tva_a_payer: Decimal
    credit_a_reporter: Decimal
    a_verifier: bool
    anomalies: list[str]


def calculer_position_tva_v2(
    *,
    tva_collectee: Decimal,
    tva_recuperable_charges: Decimal,
    tva_recuperable_immobilisations: Decimal,
    credit_anterieur: Decimal = ZERO,
    regularisations: list[Decimal] | tuple[Decimal, ...] = (),
    retenues_tva: list[Decimal] | tuple[Decimal, ...] = (),
    periodicite: str | None = None,
    prorata_applicable: bool | None = None,
    prorata_deduction: Decimal | None = None,
    retenue_applicable: bool | None = None,
    anomalies_source: list[str] | tuple[str, ...] = (),
) -> TvaPeriodeCalcul:
    """Calcule une position sans inventer de paramètre fiscal.

    Les régularisations sont des montants signés déjà validés. Les retenues
    sont conservées séparément et ne modifient pas le net tant que leur règle
    d'impact n'est pas explicitement configurée dans une évolution dédiée.
    """
    collectee = _money(tva_collectee)
    charges = _money(tva_recuperable_charges)
    immobilisations = _money(tva_recuperable_immobilisations)
    credit = max(_money(credit_anterieur), ZERO)
    adjustments = sum((_money(value) for value in regularisations), ZERO).quantize(MONEY)
    retenues = sum((abs(_money(value)) for value in retenues_tva), ZERO).quantize(MONEY)
    anomalies = list(dict.fromkeys(str(item) for item in anomalies_source if str(item).strip()))

    if periodicite is None:
        anomalies.append("Périodicité TVA de l'entreprise non configurée.")
    elif periodicite != "mensuelle":
        anomalies.append(
            f"Périodicité {periodicite} configurée : les mois affichés restent des contrôles comptables et ne sont pas validés comme périodes fiscales."
        )
    if prorata_applicable is None:
        anomalies.append("Applicabilité du prorata de déduction non configurée.")
    elif prorata_applicable:
        if prorata_deduction is None:
            anomalies.append("Prorata applicable mais valeur de prorata non configurée.")
        else:
            ratio = Decimal(str(prorata_deduction))
            if ratio < ZERO or ratio > Decimal("1"):
                anomalies.append("Prorata de déduction hors intervalle 0..1.")
            else:
                charges = (charges * ratio).quantize(MONEY, rounding=ROUND_HALF_UP)
                immobilisations = (immobilisations * ratio).quantize(MONEY, rounding=ROUND_HALF_UP)
    if retenue_applicable is None:
        anomalies.append("Applicabilité de la retenue TVA non configurée.")
    if retenues > ZERO:
        anomalies.append(
            "Retenue TVA enregistrée : son impact fiscal reste à vérifier et n'est pas appliqué automatiquement."
        )

    net = (
        collectee - charges - immobilisations - credit + adjustments
    ).quantize(MONEY)
    return TvaPeriodeCalcul(
        tva_collectee=collectee,
        tva_recuperable_charges=charges,
        tva_recuperable_immobilisations=immobilisations,
        credit_anterieur=credit,
        regularisations=adjustments,
        retenues_tva=retenues,
        tva_nette=net,
        tva_a_payer=max(net, ZERO).quantize(MONEY),
        credit_a_reporter=max(-net, ZERO).quantize(MONEY),
        a_verifier=bool(anomalies),
        anomalies=list(dict.fromkeys(anomalies)),
    )


def _periode_precedente(annee: int, mois: int) -> tuple[int, int]:
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def _configuration_tva(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> TvaConfigurationEntreprise | None:
    return db.execute(
        select(TvaConfigurationEntreprise).where(
            TvaConfigurationEntreprise.cabinet_id == cabinet_id,
            TvaConfigurationEntreprise.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()


def _credit_disponible(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    annee: int,
    mois: int,
    destination_id: uuid.UUID | None,
) -> tuple[TvaPeriode | None, Decimal]:
    previous_year, previous_month = _periode_precedente(annee, mois)
    source = db.execute(
        select(TvaPeriode).where(
            TvaPeriode.cabinet_id == cabinet_id,
            TvaPeriode.entreprise_id == entreprise_id,
            TvaPeriode.annee == previous_year,
            TvaPeriode.mois == previous_month,
            TvaPeriode.statut.in_(["validee", "cloturee"]),
            TvaPeriode.credit_a_reporter > ZERO,
        )
    ).scalar_one_or_none()
    if source is None:
        return None, ZERO

    utilisation = db.execute(
        select(TvaCreditUtilisation).where(
            TvaCreditUtilisation.cabinet_id == cabinet_id,
            TvaCreditUtilisation.entreprise_id == entreprise_id,
            TvaCreditUtilisation.periode_source_id == source.id,
        )
    ).scalar_one_or_none()
    if utilisation is not None and utilisation.periode_destination_id != destination_id:
        return None, ZERO
    return source, _money(source.credit_a_reporter)


def synchroniser_ecriture_tva(
    db: Session,
    *,
    periode: TvaPeriode,
    configuration: TvaConfigurationEntreprise | None,
) -> list[str]:
    """Crée les lignes de centralisation TVA sans jamais inventer un compte."""
    db.execute(delete(LigneComptable).where(
        LigneComptable.cabinet_id == periode.cabinet_id,
        LigneComptable.entreprise_id == periode.entreprise_id,
        LigneComptable.tva_periode_id == periode.id,
    ))

    amounts = {
        "compte_tva_collectee": _money(periode.tva_collectee),
        "compte_tva_recuperable_charges": _money(periode.tva_recuperable_charges),
        "compte_tva_recuperable_immobilisations": _money(periode.tva_recuperable_immobilisations),
        "compte_tva_a_payer": _money(periode.tva_a_payer),
        "compte_credit_tva": max(_money(periode.credit_a_reporter), _money(periode.credit_anterieur)),
    }
    if not any(value > ZERO for value in amounts.values()):
        return []
    if _money(periode.regularisations) != ZERO or _money(periode.retenues_tva) != ZERO:
        return [
            "Les régularisations ou retenues TVA exigent une écriture manuelle configurée ; aucune ligne n'a été inventée."
        ]
    if configuration is None:
        return ["Les comptes de centralisation TVA ne sont pas configurés pour cette entreprise."]

    components: list[tuple[str, Decimal, int]] = []
    # Le signe est Débit - Crédit. Les crédits antérieurs consommés sont
    # crédités, tandis qu'un nouveau crédit à reporter est débité.
    mapping = (
        ("compte_tva_collectee", _money(periode.tva_collectee), 1),
        ("compte_tva_recuperable_charges", _money(periode.tva_recuperable_charges), -1),
        ("compte_tva_recuperable_immobilisations", _money(periode.tva_recuperable_immobilisations), -1),
        ("compte_credit_tva", _money(periode.credit_anterieur), -1),
        ("compte_tva_a_payer", _money(periode.tva_a_payer), -1),
        ("compte_credit_tva", _money(periode.credit_a_reporter), 1),
    )
    missing: list[str] = []
    configured_numbers: set[str] = set()
    for field_name, amount, sign in mapping:
        if amount <= ZERO:
            continue
        number = getattr(configuration, field_name, None)
        if not number:
            missing.append(f"Compte exact non configuré : {field_name}.")
            continue
        number = str(number).strip()
        configured_numbers.add(number)
        components.append((number, amount, sign))
    if missing:
        return missing

    plan_numbers = set(db.execute(select(CompteComptableEntreprise.numero_compte).where(
        CompteComptableEntreprise.cabinet_id == periode.cabinet_id,
        CompteComptableEntreprise.entreprise_id == periode.entreprise_id,
        CompteComptableEntreprise.numero_compte.in_(configured_numbers),
        CompteComptableEntreprise.is_active.is_(True),
    )).scalars().all())
    unknown = sorted(configured_numbers - plan_numbers)
    if unknown:
        return [
            "Compte TVA absent du plan comptable actif de l'entreprise : " + ", ".join(unknown) + "."
        ]

    signed_by_account: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for number, amount, sign in components:
        signed_by_account[number] += amount * sign
    total_signed = sum(signed_by_account.values(), ZERO).quantize(MONEY, rounding=ROUND_HALF_UP)
    # Cette écriture est produite par des calculs décimaux déterministes : elle
    # doit être strictement équilibrée. La tolérance d'affichage de la Balance
    # ne doit jamais autoriser une centralisation TVA déséquilibrée en base.
    if total_signed != ZERO:
        return [f"L'écriture de centralisation TVA est déséquilibrée (écart {total_signed} MAD)."]

    entry_date = date(periode.annee, periode.mois, calendar.monthrange(periode.annee, periode.mois)[1])
    order = 1
    for number, signed in sorted(signed_by_account.items()):
        signed = signed.quantize(MONEY, rounding=ROUND_HALF_UP)
        if signed == ZERO:
            continue
        db.add(LigneComptable(
            cabinet_id=periode.cabinet_id,
            entreprise_id=periode.entreprise_id,
            tva_periode_id=periode.id,
            date_ecriture=entry_date,
            journal="TVA",
            numero_piece=f"TVA-{periode.annee}-{periode.mois:02d}",
            compte=number,
            libelle=f"Centralisation TVA {periode.mois:02d}/{periode.annee}",
            debit=signed if signed > ZERO else ZERO,
            credit=-signed if signed < ZERO else ZERO,
            ordre=order,
            origine="tva",
            est_validee=True,
        ))
        order += 1
    return []


def recalculer_periodes_tva(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    annee: int,
) -> list[TvaPeriode]:
    """Met à jour uniquement les périodes provisoires du tenant demandé."""
    base = calculer_tva_annuelle(
        db,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )
    configuration = _configuration_tva(
        db, cabinet_id=cabinet_id, entreprise_id=entreprise_id
    )
    existing = {
        item.mois: item
        for item in db.execute(
            select(TvaPeriode).where(
                TvaPeriode.cabinet_id == cabinet_id,
                TvaPeriode.entreprise_id == entreprise_id,
                TvaPeriode.annee == annee,
            )
        ).scalars().all()
    }

    results: list[TvaPeriode] = []
    now = datetime.now(timezone.utc)
    for month_base in base.mensualites:
        periode = existing.get(month_base.mois)
        if periode is None:
            periode = TvaPeriode(
                cabinet_id=cabinet_id,
                entreprise_id=entreprise_id,
                annee=annee,
                mois=month_base.mois,
            )
            db.add(periode)
            db.flush()
        if periode.statut in {"validee", "cloturee"}:
            results.append(periode)
            continue

        source_credit, credit = _credit_disponible(
            db,
            cabinet_id=cabinet_id,
            entreprise_id=entreprise_id,
            annee=annee,
            mois=month_base.mois,
            destination_id=periode.id,
        )
        regularisations = db.execute(
            select(TvaRegularisation).where(
                TvaRegularisation.cabinet_id == cabinet_id,
                TvaRegularisation.entreprise_id == entreprise_id,
                TvaRegularisation.periode_id == periode.id,
                TvaRegularisation.statut == "validee",
            )
        ).scalars().all()
        ordinary = [r.montant_signe for r in regularisations if r.nature != "retenue"]
        retained = [r.montant_signe for r in regularisations if r.nature == "retenue"]
        calculation = calculer_position_tva_v2(
            tva_collectee=month_base.tva_collectee,
            tva_recuperable_charges=month_base.tva_deductible_charges,
            tva_recuperable_immobilisations=month_base.tva_deductible_immobilisations,
            credit_anterieur=credit,
            regularisations=ordinary,
            retenues_tva=retained,
            periodicite=configuration.periodicite if configuration else None,
            prorata_applicable=configuration.prorata_applicable if configuration else None,
            prorata_deduction=configuration.prorata_deduction if configuration else None,
            retenue_applicable=configuration.retenue_applicable if configuration else None,
            anomalies_source=month_base.raisons_verification,
        )
        periode.tva_collectee = calculation.tva_collectee
        periode.tva_recuperable_charges = calculation.tva_recuperable_charges
        periode.tva_recuperable_immobilisations = calculation.tva_recuperable_immobilisations
        periode.credit_anterieur = calculation.credit_anterieur
        periode.regularisations = calculation.regularisations
        periode.retenues_tva = calculation.retenues_tva
        periode.tva_nette = calculation.tva_nette
        periode.tva_a_payer = calculation.tva_a_payer
        periode.credit_a_reporter = calculation.credit_a_reporter
        periode.credit_source_periode_id = source_credit.id if source_credit else None
        periode.calcul_provisoire_at = now
        line_anomalies = synchroniser_ecriture_tva(
            db,
            periode=periode,
            configuration=configuration,
        )
        periode.anomalies = list(dict.fromkeys([*calculation.anomalies, *line_anomalies]))
        periode.a_verifier = calculation.a_verifier or bool(line_anomalies)
        periode.statut_comptable = (
            "a_verifier"
            if periode.a_verifier
            else "saisie_topaze"
            if periode.topaze_entered_at is not None
            else "prete_topaze"
        )
        if periode.declared_at is not None:
            periode.statut_declaration = "declaree"
        elif periode.date_limite_declaration and date.today() > periode.date_limite_declaration:
            periode.statut_declaration = "en_retard"
        elif periode.a_verifier:
            periode.statut_declaration = "a_verifier"
        else:
            periode.statut_declaration = "prete_a_declarer"
        results.append(periode)
    db.flush()
    return results


def valider_periode_tva(
    db: Session,
    *,
    periode: TvaPeriode,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TvaPeriode:
    if periode.cabinet_id != cabinet_id or periode.entreprise_id != entreprise_id:
        raise ValueError("Période TVA hors du cabinet ou de l'entreprise.")
    if periode.a_verifier:
        raise ValueError("La période TVA contient des anomalies à vérifier.")
    if periode.statut == "cloturee":
        raise ValueError("Une période TVA clôturée ne peut pas être revalidée.")

    if periode.credit_source_periode_id and _money(periode.credit_anterieur) > ZERO:
        existing = db.execute(
            select(TvaCreditUtilisation).where(
                TvaCreditUtilisation.cabinet_id == cabinet_id,
                TvaCreditUtilisation.entreprise_id == entreprise_id,
                TvaCreditUtilisation.periode_source_id == periode.credit_source_periode_id,
            )
        ).scalar_one_or_none()
        if existing is not None and existing.periode_destination_id != periode.id:
            raise ValueError("Ce crédit TVA a déjà été utilisé par une autre période.")
        if existing is None:
            db.add(
                TvaCreditUtilisation(
                    cabinet_id=cabinet_id,
                    entreprise_id=entreprise_id,
                    periode_source_id=periode.credit_source_periode_id,
                    periode_destination_id=periode.id,
                    montant_utilise=periode.credit_anterieur,
                    utilise_at=datetime.now(timezone.utc),
                    utilise_par=user_id,
                )
            )
    periode.statut = "validee"
    periode.statut_comptable = "prete_topaze"
    periode.validee_at = datetime.now(timezone.utc)
    periode.validee_par = user_id
    db.flush()
    return periode
