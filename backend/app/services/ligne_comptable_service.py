"""Moteur de lignes Débit / Crédit, Grand Livre et Balance.

Principes de sécurité comptable de cette V1 :
- aucune ligne n'est créée si un compte obligatoire manque ;
- aucun numéro de compte n'est inventé ;
- aucune différence d'arrondi n'est forcée dans un compte inconnu ;
- les lignes du Grand Livre sont toujours exprimées en MAD ;
- le Grand Livre et la Balance utilisent uniquement des lignes validées ;
- paiements partiels, règlements groupés et écarts de change ne sont pas
  automatisés dans cette V1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.ecriture import EcritureComptable
from app.models.enums import (
    StatutValidationEnum,
    TypeEcritureEnum,
    TypeMouvementBancaireEnum,
)
from app.models.ligne_comptable import LigneComptable
from app.models.tva_periode import TvaPeriode
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

STATUTS_RAPPROCHEMENT_COMPTABILISABLES = {"automatique", "confirme"}
STATUTS_ECRITURES_COMPTABILISABLES = {
    StatutValidationEnum.PRETE_TOPAZE,
    StatutValidationEnum.SAISIE_TOPAZE,
    StatutValidationEnum.VALIDE,
}


@dataclass(slots=True)
class GenerationLignesResultat:
    applicable: bool
    complet: bool
    lignes: list[dict] = field(default_factory=list)
    raisons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReconstructionResultat:
    ecritures_total: int = 0
    ecritures_completes: int = 0
    ecritures_incompletes: int = 0
    mouvements_total: int = 0
    mouvements_complets: int = 0
    mouvements_incomplets: int = 0
    lignes_total: int = 0


def _money(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _texte(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _value(value: object | None) -> str:
    return value.value if hasattr(value, "value") else str(value or "")


def _libelle_ecriture(ecriture: EcritureComptable) -> str:
    return (
        _texte(getattr(ecriture, "libelle", None))
        or " ".join(
            part
            for part in (
                _texte(ecriture.tiers),
                _texte(ecriture.numero_piece),
            )
            if part
        )
        or "Écriture comptable"
    )[:500]


def construire_lignes_facture(
    ecriture: EcritureComptable,
) -> GenerationLignesResultat:
    """Construit une proposition Débit/Crédit sans toucher à la base."""
    type_value = (
        ecriture.type_ecriture.value
        if hasattr(ecriture.type_ecriture, "value")
        else str(ecriture.type_ecriture)
    )

    if type_value not in {
        TypeEcritureEnum.ACHAT.value,
        TypeEcritureEnum.VENTE.value,
    }:
        return GenerationLignesResultat(
            applicable=False,
            complet=True,
        )

    raisons: list[str] = []
    date_piece = ecriture.date_piece
    compte_tiers = _texte(getattr(ecriture, "compte_tiers", None))
    compte_ht = _texte(getattr(ecriture, "compte_ht", None))
    compte_tva = _texte(getattr(ecriture, "compte_tva", None))

    ht = _money(ecriture.montant_ht)
    tva = _money(ecriture.montant_tva)
    ttc = _money(ecriture.montant_ttc)

    if date_piece is None:
        raisons.append("Date de pièce absente : lignes Débit/Crédit non générées.")
    if not compte_tiers:
        raisons.append("Compte tiers absent : lignes Débit/Crédit non générées.")
    if not compte_ht:
        raisons.append("Compte HT/produit absent : lignes Débit/Crédit non générées.")
    if ht is None:
        raisons.append("Montant HT absent : lignes Débit/Crédit non générées.")
    if tva is None:
        raisons.append(
            "Montant TVA absent : ComptaFlow refuse de déduire automatiquement qu'il vaut zéro."
        )
    if ttc is None or ttc <= ZERO:
        raisons.append("Montant TTC absent ou nul : lignes Débit/Crédit non générées.")

    if tva is not None and tva > ZERO and not compte_tva:
        raisons.append("Compte TVA absent alors que la TVA est positive.")

    if ht is not None and tva is not None and ttc is not None:
        if (ht + tva).quantize(MONEY) != ttc:
            raisons.append(
                "Les montants comptables MAD ne s'équilibrent pas exactement au centime : "
                f"HT {ht} + TVA {tva} != TTC {ttc}."
            )

    if raisons:
        return GenerationLignesResultat(
            applicable=True,
            complet=False,
            raisons=raisons,
        )

    assert date_piece is not None
    assert compte_tiers is not None
    assert compte_ht is not None
    assert ht is not None
    assert tva is not None
    assert ttc is not None

    libelle = _libelle_ecriture(ecriture)
    piece = _texte(ecriture.numero_piece)
    lignes: list[dict] = []

    def add(compte: str, debit: Decimal, credit: Decimal) -> None:
        lignes.append(
            {
                "date_ecriture": date_piece,
                "numero_piece": piece,
                "compte": compte,
                "libelle": libelle,
                "debit": debit,
                "credit": credit,
            }
        )

    if type_value == TypeEcritureEnum.ACHAT.value:
        add(compte_ht, ht, ZERO)
        if tva > ZERO:
            assert compte_tva is not None
            add(compte_tva, tva, ZERO)
        add(compte_tiers, ZERO, ttc)
        journal = "ACH"
    else:
        add(compte_tiers, ttc, ZERO)
        add(compte_ht, ZERO, ht)
        if tva > ZERO:
            assert compte_tva is not None
            add(compte_tva, ZERO, tva)
        journal = "VTE"

    total_debit = sum((item["debit"] for item in lignes), ZERO)
    total_credit = sum((item["credit"] for item in lignes), ZERO)

    if total_debit != total_credit:
        return GenerationLignesResultat(
            applicable=True,
            complet=False,
            raisons=[
                "Écriture non équilibrée : "
                f"débit {total_debit} != crédit {total_credit}."
            ],
        )

    for index, ligne in enumerate(lignes, start=1):
        ligne["ordre"] = index
        ligne["journal"] = journal

    return GenerationLignesResultat(
        applicable=True,
        complet=True,
        lignes=lignes,
    )


def synchroniser_lignes_facture(
    db: Session,
    ecriture: EcritureComptable,
) -> GenerationLignesResultat:
    """Remplace les anciennes lignes de facture par la proposition actuelle."""
    db.flush()
    db.query(LigneComptable).filter(
        LigneComptable.ecriture_id == ecriture.id
    ).delete(synchronize_session=False)

    resultat = construire_lignes_facture(ecriture)
    if not resultat.applicable or not resultat.complet:
        return resultat

    est_validee = ecriture.statut_validation in STATUTS_ECRITURES_COMPTABILISABLES

    for item in resultat.lignes:
        db.add(
            LigneComptable(
                cabinet_id=ecriture.cabinet_id,
                entreprise_id=ecriture.entreprise_id,
                ecriture_id=ecriture.id,
                mouvement_bancaire_id=None,
                date_ecriture=item["date_ecriture"],
                journal=item["journal"],
                numero_piece=item["numero_piece"],
                compte=item["compte"],
                libelle=item["libelle"],
                debit=item["debit"],
                credit=item["credit"],
                ordre=item["ordre"],
                origine="facture",
                est_validee=est_validee,
            )
        )

    db.flush()
    return resultat


def _ligne_banque_item(
    *,
    ordre: int,
    mouvement: MouvementBancaire,
    compte: str,
    debit: Decimal,
    credit: Decimal,
    libelle: str,
    numero_piece: str | None,
) -> dict:
    return {
        "ordre": ordre,
        "journal": "BQ",
        "date_ecriture": mouvement.date_operation,
        "numero_piece": numero_piece,
        "compte": compte,
        "libelle": libelle[:500],
        "debit": debit,
        "credit": credit,
    }


def construire_lignes_banque(
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable | None,
) -> GenerationLignesResultat:
    """Compatibilité V1 : construit un règlement simple sur une facture."""
    if ecriture is None:
        return GenerationLignesResultat(
            applicable=True,
            complet=False,
            raisons=["Mouvement bancaire sans facture rapprochée."],
        )
    montant = _money(mouvement.montant)
    compte_banque = _texte(mouvement.compte_banque)
    compte_tiers = _texte(ecriture.compte_tiers)
    raisons: list[str] = []
    if mouvement.statut_rapprochement not in STATUTS_RAPPROCHEMENT_COMPTABILISABLES:
        return GenerationLignesResultat(applicable=False, complet=True)
    if ecriture.statut_validation not in STATUTS_ECRITURES_COMPTABILISABLES:
        raisons.append("La facture rapprochée n'est pas encore validée.")
    if not compte_banque:
        raisons.append("Compte banque exact absent.")
    if not compte_tiers:
        raisons.append("Compte tiers exact absent.")
    if montant is None or montant <= ZERO:
        raisons.append("Montant bancaire absent ou nul.")
    montant_facture = _money(ecriture.montant_ttc)
    if montant is not None and montant_facture is not None and montant != montant_facture:
        raisons.append(
            "Paiement partiel/groupé ou écart de change détecté : "
            "utiliser les allocations Banque V2."
        )
    if raisons:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=raisons)

    assert montant is not None and compte_banque and compte_tiers
    type_mouvement = getattr(mouvement.type_mouvement, "value", mouvement.type_mouvement)
    type_ecriture = getattr(ecriture.type_ecriture, "value", ecriture.type_ecriture)
    libelle = (_texte(mouvement.libelle) or _libelle_ecriture(ecriture))[:500]
    piece = _texte(mouvement.reference) or _texte(ecriture.numero_piece)
    if type_mouvement == TypeMouvementBancaireEnum.DEBIT.value:
        if type_ecriture != TypeEcritureEnum.ACHAT.value:
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Débit bancaire incompatible avec cette facture."])
        sens = [(compte_tiers, montant, ZERO), (compte_banque, ZERO, montant)]
    elif type_mouvement == TypeMouvementBancaireEnum.CREDIT.value:
        if type_ecriture != TypeEcritureEnum.VENTE.value:
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Crédit bancaire incompatible avec cette facture."])
        sens = [(compte_banque, montant, ZERO), (compte_tiers, ZERO, montant)]
    else:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=["Type bancaire non supporté."])

    return GenerationLignesResultat(
        applicable=True,
        complet=True,
        lignes=[
            _ligne_banque_item(
                ordre=i,
                mouvement=mouvement,
                compte=compte,
                debit=debit,
                credit=credit,
                libelle=libelle,
                numero_piece=piece,
            )
            for i, (compte, debit, credit) in enumerate(sens, start=1)
        ],
    )


def _construire_lignes_operation_speciale(
    db: Session,
    mouvement: MouvementBancaire,
) -> GenerationLignesResultat:
    nature = _texte(getattr(mouvement, "nature_operation", None)) or "reglement_facture"
    if nature == "reglement_facture":
        return GenerationLignesResultat(applicable=False, complet=True)

    compte_banque = _texte(mouvement.compte_banque)
    montant = _money(mouvement.montant)
    if not compte_banque:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=["Compte bancaire exact non configuré."])
    if montant is None or montant <= ZERO:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=["Montant bancaire absent ou nul."])

    libelle = _texte(mouvement.libelle) or nature.replace("_", " ").title()
    piece = _texte(mouvement.reference)
    type_mouvement = getattr(mouvement.type_mouvement, "value", mouvement.type_mouvement)

    if nature == "virement_interne":
        if mouvement.mouvement_lie_id is None:
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Virement interne sans mouvement opposé lié."])
        autre = db.get(MouvementBancaire, mouvement.mouvement_lie_id)
        if autre is None or not _texte(autre.compte_banque):
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Compte bancaire destination/source introuvable."])
        if _money(autre.montant) != montant:
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Les deux côtés du virement interne n'ont pas le même montant."])
        # Une seule écriture : le mouvement DEBIT porte l'écriture complète.
        if type_mouvement == TypeMouvementBancaireEnum.CREDIT.value:
            return GenerationLignesResultat(applicable=False, complet=True)
        destination = _texte(autre.compte_banque)
        assert destination is not None
        if destination == compte_banque:
            return GenerationLignesResultat(applicable=True, complet=False, raisons=["Source et destination utilisent le même compte bancaire."])
        return GenerationLignesResultat(
            applicable=True,
            complet=True,
            lignes=[
                _ligne_banque_item(ordre=1, mouvement=mouvement, compte=destination, debit=montant, credit=ZERO, libelle=libelle, numero_piece=piece),
                _ligne_banque_item(ordre=2, mouvement=mouvement, compte=compte_banque, debit=ZERO, credit=montant, libelle=libelle, numero_piece=piece),
            ],
        )

    contrepartie = _texte(getattr(mouvement, "compte_contrepartie", None))
    if not contrepartie:
        return GenerationLignesResultat(
            applicable=True,
            complet=False,
            raisons=[
                "Compte de contrepartie exact obligatoire pour cette opération spéciale. "
                "ComptaFlow refuse d'en inventer un."
            ],
        )

    if type_mouvement == TypeMouvementBancaireEnum.DEBIT.value:
        sens = [(contrepartie, montant, ZERO), (compte_banque, ZERO, montant)]
    elif type_mouvement == TypeMouvementBancaireEnum.CREDIT.value:
        sens = [(compte_banque, montant, ZERO), (contrepartie, ZERO, montant)]
    else:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=["Type bancaire non supporté."])

    return GenerationLignesResultat(
        applicable=True,
        complet=True,
        lignes=[
            _ligne_banque_item(ordre=i, mouvement=mouvement, compte=compte, debit=debit, credit=credit, libelle=libelle, numero_piece=piece)
            for i, (compte, debit, credit) in enumerate(sens, start=1)
        ],
    )


def _construire_lignes_allocations(
    db: Session,
    mouvement: MouvementBancaire,
) -> GenerationLignesResultat:
    allocations = (
        db.query(RapprochementBancaireAllocation)
        .filter(
            RapprochementBancaireAllocation.cabinet_id == mouvement.cabinet_id,
            RapprochementBancaireAllocation.entreprise_id == mouvement.entreprise_id,
            RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
            RapprochementBancaireAllocation.statut.in_(["automatique", "confirme"]),
        )
        .order_by(RapprochementBancaireAllocation.created_at.asc())
        .all()
    )

    if not allocations:
        # Compatibilité avec les rapprochements V1 existants avant migration V2.
        if mouvement.ecriture_rapprochee_id is not None and mouvement.statut_rapprochement in STATUTS_RAPPROCHEMENT_COMPTABILISABLES:
            legacy_entry = db.get(EcritureComptable, mouvement.ecriture_rapprochee_id)
            return construire_lignes_banque(mouvement, legacy_entry)
        return GenerationLignesResultat(applicable=False, complet=True)

    compte_banque = _texte(mouvement.compte_banque)
    montant_mouvement = _money(mouvement.montant)
    raisons: list[str] = []
    if not compte_banque:
        raisons.append("Compte banque exact absent du plan/configuration de l'entreprise.")
    if montant_mouvement is None or montant_mouvement <= ZERO:
        raisons.append("Montant bancaire absent ou nul.")

    rows: list[
        tuple[
            EcritureComptable,
            Decimal,
            Decimal,
            str,
            RapprochementBancaireAllocation,
        ]
    ] = []
    total = ZERO
    expected = TypeEcritureEnum.ACHAT if getattr(mouvement.type_mouvement, "value", mouvement.type_mouvement) == TypeMouvementBancaireEnum.DEBIT.value else TypeEcritureEnum.VENTE
    for allocation in allocations:
        entry = db.get(EcritureComptable, allocation.ecriture_id)
        amount = _money(
            allocation.montant_reglement_mad or allocation.montant_affecte
        )
        carrying_amount = _money(
            allocation.valeur_comptable_mad or allocation.montant_affecte
        )
        if entry is None:
            raisons.append("Une facture affectée n'existe plus.")
            continue
        if (
            allocation.cabinet_id != mouvement.cabinet_id
            or allocation.entreprise_id != mouvement.entreprise_id
            or entry.cabinet_id != mouvement.cabinet_id
            or entry.entreprise_id != mouvement.entreprise_id
        ):
            raisons.append("Une allocation n'appartient pas au même cabinet et à la même entreprise.")
            continue
        if entry.statut_validation not in STATUTS_ECRITURES_COMPTABILISABLES:
            raisons.append(f"Facture {entry.numero_piece or entry.id} non validée.")
        if entry.type_ecriture != expected:
            raisons.append(f"Facture {entry.numero_piece or entry.id} incompatible avec le sens bancaire.")
        account = _texte(entry.compte_tiers)
        if not account:
            raisons.append(f"Compte tiers absent pour {entry.numero_piece or entry.id}.")
        if amount is None or amount <= ZERO:
            raisons.append(f"Montant d'affectation invalide pour {entry.numero_piece or entry.id}.")
            continue
        if carrying_amount is None or carrying_amount <= ZERO:
            raisons.append(f"Valeur comptable initiale absente pour {entry.numero_piece or entry.id}.")
            continue
        if allocation.statut_ecart_change == "a_verifier":
            raisons.append(
                allocation.raison_ecart_change
                or f"Écart de change à vérifier pour {entry.numero_piece or entry.id}."
            )
        total += amount
        if account:
            rows.append((entry, amount, carrying_amount, account, allocation))

    if montant_mouvement is not None and abs(total - montant_mouvement) > MONEY:
        raisons.append(
            f"Le total affecté ({total}) ne couvre pas exactement le mouvement ({montant_mouvement})."
        )
    if raisons:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=raisons)

    assert compte_banque is not None and montant_mouvement is not None
    libelle = _texte(mouvement.libelle) or "Règlement bancaire"
    piece = _texte(mouvement.reference)
    lines: list[dict] = []
    order = 1
    type_mouvement = getattr(mouvement.type_mouvement, "value", mouvement.type_mouvement)
    if type_mouvement == TypeMouvementBancaireEnum.DEBIT.value:
        for entry, amount, carrying_amount, account, allocation in rows:
            lines.append(_ligne_banque_item(
                ordre=order, mouvement=mouvement, compte=account,
                debit=carrying_amount, credit=ZERO,
                libelle=f"{libelle} - {entry.numero_piece or entry.tiers or 'facture'}",
                numero_piece=piece or _texte(entry.numero_piece),
            ))
            order += 1
            ecart = _money(allocation.ecart_change_mad) or ZERO
            if ecart > ZERO:
                fx_account = _texte(allocation.compte_ecart_change)
                nature = _texte(allocation.nature_ecart_change)
                if not fx_account or nature not in {"gain", "perte"}:
                    return GenerationLignesResultat(
                        applicable=True,
                        complet=False,
                        raisons=["Compte exact de gain/perte de change absent ou ambigu."],
                    )
                lines.append(_ligne_banque_item(
                    ordre=order,
                    mouvement=mouvement,
                    compte=fx_account,
                    debit=ecart if nature == "perte" else ZERO,
                    credit=ecart if nature == "gain" else ZERO,
                    libelle=f"Écart de change - {entry.numero_piece or entry.tiers or 'facture'}",
                    numero_piece=piece or _texte(entry.numero_piece),
                ))
                order += 1
        lines.append(_ligne_banque_item(
            ordre=order, mouvement=mouvement, compte=compte_banque,
            debit=ZERO, credit=montant_mouvement,
            libelle=libelle, numero_piece=piece,
        ))
    else:
        lines.append(_ligne_banque_item(
            ordre=order, mouvement=mouvement, compte=compte_banque,
            debit=montant_mouvement, credit=ZERO,
            libelle=libelle, numero_piece=piece,
        ))
        order += 1
        for entry, amount, carrying_amount, account, allocation in rows:
            lines.append(_ligne_banque_item(
                ordre=order, mouvement=mouvement, compte=account,
                debit=ZERO, credit=carrying_amount,
                libelle=f"{libelle} - {entry.numero_piece or entry.tiers or 'facture'}",
                numero_piece=piece or _texte(entry.numero_piece),
            ))
            order += 1
            ecart = _money(allocation.ecart_change_mad) or ZERO
            if ecart > ZERO:
                fx_account = _texte(allocation.compte_ecart_change)
                nature = _texte(allocation.nature_ecart_change)
                if not fx_account or nature not in {"gain", "perte"}:
                    return GenerationLignesResultat(
                        applicable=True,
                        complet=False,
                        raisons=["Compte exact de gain/perte de change absent ou ambigu."],
                    )
                lines.append(_ligne_banque_item(
                    ordre=order,
                    mouvement=mouvement,
                    compte=fx_account,
                    debit=ecart if nature == "perte" else ZERO,
                    credit=ecart if nature == "gain" else ZERO,
                    libelle=f"Écart de change - {entry.numero_piece or entry.tiers or 'facture'}",
                    numero_piece=piece or _texte(entry.numero_piece),
                ))
                order += 1

    debit_total = sum((line["debit"] for line in lines), ZERO)
    credit_total = sum((line["credit"] for line in lines), ZERO)
    if debit_total != credit_total:
        return GenerationLignesResultat(applicable=True, complet=False, raisons=[f"Écriture Banque déséquilibrée : {debit_total} != {credit_total}."])
    return GenerationLignesResultat(applicable=True, complet=True, lignes=lines)


def synchroniser_lignes_banque(
    db: Session,
    mouvement: MouvementBancaire,
) -> GenerationLignesResultat:
    """Synchronise les lignes Banque V2 de manière idempotente."""
    db.flush()
    db.query(LigneComptable).filter(
        LigneComptable.mouvement_bancaire_id == mouvement.id
    ).delete(synchronize_session=False)

    if getattr(mouvement, "nature_operation", "reglement_facture") != "reglement_facture":
        resultat = _construire_lignes_operation_speciale(db, mouvement)
    else:
        resultat = _construire_lignes_allocations(db, mouvement)

    if not resultat.applicable or not resultat.complet:
        return resultat

    for item in resultat.lignes:
        db.add(
            LigneComptable(
                cabinet_id=mouvement.cabinet_id,
                entreprise_id=mouvement.entreprise_id,
                ecriture_id=None,
                mouvement_bancaire_id=mouvement.id,
                date_ecriture=item["date_ecriture"],
                journal=item["journal"],
                numero_piece=item["numero_piece"],
                compte=item["compte"],
                libelle=item["libelle"],
                debit=item["debit"],
                credit=item["credit"],
                ordre=item["ordre"],
                origine="banque",
                est_validee=True,
            )
        )
    db.flush()
    return resultat


def supprimer_lignes_banque(db: Session, mouvement_id: uuid.UUID) -> None:
    db.query(LigneComptable).filter(
        LigneComptable.mouvement_bancaire_id == mouvement_id
    ).delete(synchronize_session=False)

def _labels_comptes(
    db: Session,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> dict[str, str]:
    rows = db.execute(
        select(
            CompteComptableEntreprise.numero_compte,
            CompteComptableEntreprise.libelle,
        ).where(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
        )
    ).all()
    return {str(numero): str(libelle) for numero, libelle in rows}


def _query_lignes_validees(
    db: Session,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    date_debut: date | None,
    date_fin: date | None,
    compte_prefix: str | None = None,
    journal: str | None = None,
    statut_topaze: StatutValidationEnum | None = None,
    tiers: str | None = None,
    recherche: str | None = None,
):
    query = select(LigneComptable).outerjoin(
        EcritureComptable, LigneComptable.ecriture_id == EcritureComptable.id
    ).where(
        LigneComptable.cabinet_id == cabinet_id,
        LigneComptable.entreprise_id == entreprise_id,
        LigneComptable.est_validee.is_(True),
    )
    if date_debut is not None:
        query = query.where(LigneComptable.date_ecriture >= date_debut)
    if date_fin is not None:
        query = query.where(LigneComptable.date_ecriture <= date_fin)
    if compte_prefix:
        query = query.where(LigneComptable.compte.startswith(compte_prefix.strip()))
    if journal:
        query = query.where(LigneComptable.journal == journal.strip().upper())
    if statut_topaze is not None:
        query = query.where(EcritureComptable.statut_validation == statut_topaze)
    if tiers:
        query = query.where(EcritureComptable.tiers.ilike(f"%{tiers.strip()}%"))
    if recherche:
        pattern = f"%{recherche.strip()}%"
        query = query.where(
            (LigneComptable.numero_piece.ilike(pattern))
            | (LigneComptable.libelle.ilike(pattern))
        )
    return query


def obtenir_grand_livre(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
    compte_prefix: str | None = None,
    journal: str | None = None,
    statut_topaze: StatutValidationEnum | None = None,
    tiers: str | None = None,
    recherche: str | None = None,
) -> dict:
    labels = _labels_comptes(db, cabinet_id, entreprise_id)

    lignes = db.execute(
        _query_lignes_validees(
            db,
            cabinet_id,
            entreprise_id,
            date_debut,
            date_fin,
            compte_prefix,
            journal,
            statut_topaze,
            tiers,
            recherche,
        ).order_by(
            LigneComptable.compte.asc(),
            LigneComptable.date_ecriture.asc(),
            LigneComptable.created_at.asc(),
            LigneComptable.ordre.asc(),
        )
    ).scalars().all()

    entry_ids = {line.ecriture_id for line in lignes if line.ecriture_id is not None}
    entries = db.execute(
        select(EcritureComptable).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.id.in_(entry_ids),
        )
    ).scalars().all() if entry_ids else []
    entry_map = {entry.id: entry for entry in entries}
    tva_ids = {line.tva_periode_id for line in lignes if line.tva_periode_id is not None}
    tva_periods = db.execute(select(TvaPeriode).where(
        TvaPeriode.cabinet_id == cabinet_id,
        TvaPeriode.entreprise_id == entreprise_id,
        TvaPeriode.id.in_(tva_ids),
    )).scalars().all() if tva_ids else []
    tva_map = {period.id: period for period in tva_periods}

    soldes_initiaux: dict[str, Decimal] = {}
    if date_debut is not None:
        opening_query = select(LigneComptable).where(
            LigneComptable.cabinet_id == cabinet_id,
            LigneComptable.entreprise_id == entreprise_id,
            LigneComptable.est_validee.is_(True),
            LigneComptable.date_ecriture < date_debut,
        )
        if compte_prefix:
            opening_query = opening_query.where(
                LigneComptable.compte.startswith(compte_prefix.strip())
            )
        opening = db.execute(opening_query).scalars().all()
        for ligne in opening:
            soldes_initiaux[ligne.compte] = (
                soldes_initiaux.get(ligne.compte, ZERO)
                + (_money(ligne.debit) or ZERO)
                - (_money(ligne.credit) or ZERO)
            )

    groupes: dict[str, dict] = {}
    total_debit = ZERO
    total_credit = ZERO

    for ligne in lignes:
        compte = ligne.compte
        if compte not in groupes:
            groupes[compte] = {
                "compte": compte,
                "libelle_compte": labels.get(compte),
                "solde_initial": soldes_initiaux.get(compte, ZERO),
                "total_debit": ZERO,
                "total_credit": ZERO,
                "lignes": [],
            }

        groupe = groupes[compte]
        debit = _money(ligne.debit) or ZERO
        credit = _money(ligne.credit) or ZERO
        groupe["total_debit"] += debit
        groupe["total_credit"] += credit
        total_debit += debit
        total_credit += credit

        solde_cumule = (
            groupe["solde_initial"]
            + groupe["total_debit"]
            - groupe["total_credit"]
        )
        groupe["lignes"].append(
            {
                "id": ligne.id,
                "date_ecriture": ligne.date_ecriture,
                "journal": ligne.journal,
                "numero_piece": ligne.numero_piece,
                "compte": ligne.compte,
                "libelle": ligne.libelle,
                "debit": debit,
                "credit": credit,
                "solde_cumule": solde_cumule,
                "origine": ligne.origine,
                "ecriture_id": ligne.ecriture_id,
                "mouvement_bancaire_id": ligne.mouvement_bancaire_id,
                "regularisation_cloture_id": ligne.regularisation_cloture_id,
                "tva_periode_id": ligne.tva_periode_id,
                "document_id": entry_map[ligne.ecriture_id].document_id if ligne.ecriture_id in entry_map else None,
                "tiers": entry_map[ligne.ecriture_id].tiers if ligne.ecriture_id in entry_map else None,
                "statut_topaze": (
                    _value(entry_map[ligne.ecriture_id].statut_validation)
                    if ligne.ecriture_id in entry_map
                    else tva_map[ligne.tva_periode_id].statut_comptable
                    if ligne.tva_periode_id in tva_map
                    else None
                ),
            }
        )

    comptes = []
    for compte in sorted(groupes):
        groupe = groupes[compte]
        groupe["solde_final"] = (
            groupe["solde_initial"]
            + groupe["total_debit"]
            - groupe["total_credit"]
        )
        groupe["solde_debiteur"] = max(groupe["solde_final"], ZERO)
        groupe["solde_crediteur"] = max(-groupe["solde_final"], ZERO)
        comptes.append(groupe)

    return {
        "entreprise_id": entreprise_id,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "nombre_comptes": len(comptes),
        "nombre_lignes": len(lignes),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "equilibre": abs(total_debit - total_credit) <= MONEY,
        "comptes": comptes,
    }


def obtenir_balance(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    date_debut: date | None = None,
    date_fin: date | None = None,
) -> dict:
    labels = _labels_comptes(db, cabinet_id, entreprise_id)
    lignes = db.execute(
        _query_lignes_validees(
            db,
            cabinet_id,
            entreprise_id,
            date_debut,
            date_fin,
        ).order_by(LigneComptable.compte.asc())
    ).scalars().all()

    groupes: dict[str, dict[str, Decimal]] = {}
    for ligne in lignes:
        compte = ligne.compte
        if compte not in groupes:
            groupes[compte] = {"debit": ZERO, "credit": ZERO}
        groupes[compte]["debit"] += _money(ligne.debit) or ZERO
        groupes[compte]["credit"] += _money(ligne.credit) or ZERO

    rows = []
    total_debit = ZERO
    total_credit = ZERO
    total_solde_debiteur = ZERO
    total_solde_crediteur = ZERO

    for compte in sorted(groupes):
        debit = groupes[compte]["debit"]
        credit = groupes[compte]["credit"]
        solde = debit - credit
        solde_debiteur = solde if solde > ZERO else ZERO
        solde_crediteur = -solde if solde < ZERO else ZERO

        rows.append(
            {
                "compte": compte,
                "libelle_compte": labels.get(compte),
                "total_debit": debit,
                "total_credit": credit,
                "solde_debiteur": solde_debiteur,
                "solde_crediteur": solde_crediteur,
            }
        )
        total_debit += debit
        total_credit += credit
        total_solde_debiteur += solde_debiteur
        total_solde_crediteur += solde_crediteur

    ecart = (total_debit - total_credit).quantize(MONEY)
    comptes_inconnus = sum(1 for row in rows if row["compte"] not in labels)
    entry_query = select(EcritureComptable.id).where(
        EcritureComptable.cabinet_id == cabinet_id,
        EcritureComptable.entreprise_id == entreprise_id,
        EcritureComptable.statut_validation == StatutValidationEnum.PRETE_TOPAZE,
    )
    if date_debut is not None:
        entry_query = entry_query.where(EcritureComptable.date_piece >= date_debut)
    if date_fin is not None:
        entry_query = entry_query.where(EcritureComptable.date_piece <= date_fin)
    non_saisies = len(db.execute(entry_query).scalars().all())
    anomalies: list[str] = []
    if abs(ecart) > MONEY:
        anomalies.append(f"Écart Débit/Crédit de {ecart} MAD.")
    if comptes_inconnus:
        anomalies.append(f"{comptes_inconnus} compte(s) absent(s) du plan comptable actif.")
    if non_saisies:
        anomalies.append(f"{non_saisies} écriture(s) prête(s) non encore saisie(s) dans Topaze.")
    return {
        "entreprise_id": entreprise_id,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "nombre_comptes": len(rows),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "total_solde_debiteur": total_solde_debiteur,
        "total_solde_crediteur": total_solde_crediteur,
        "equilibree": abs(ecart) <= MONEY,
        "ecart": ecart,
        "tolerance": MONEY,
        "comptes_inconnus": comptes_inconnus,
        "ecritures_non_saisies_topaze": non_saisies,
        "anomalies": anomalies,
        "lignes": rows,
    }


def reconstruire_lignes_entreprise(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> ReconstructionResultat:
    """Recrée toutes les lignes à partir des données déjà présentes."""
    resultat = ReconstructionResultat()

    ecritures = db.execute(
        select(EcritureComptable).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
        )
    ).scalars().all()

    for ecriture in ecritures:
        generation = synchroniser_lignes_facture(db, ecriture)
        if not generation.applicable:
            continue
        resultat.ecritures_total += 1
        if generation.complet:
            resultat.ecritures_completes += 1
            resultat.lignes_total += len(generation.lignes)
        else:
            resultat.ecritures_incompletes += 1

    mouvements = db.execute(
        select(MouvementBancaire).where(
            MouvementBancaire.cabinet_id == cabinet_id,
            MouvementBancaire.entreprise_id == entreprise_id,
        )
    ).scalars().all()

    for mouvement in mouvements:
        generation = synchroniser_lignes_banque(db, mouvement)
        if not generation.applicable:
            continue
        resultat.mouvements_total += 1
        if generation.complet:
            resultat.mouvements_complets += 1
            resultat.lignes_total += len(generation.lignes)
        else:
            resultat.mouvements_incomplets += 1

    db.flush()
    return resultat
