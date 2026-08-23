"""Rapprochement bancaire Banque V2.

Banque V2 garde les règles sûres de la V1 et ajoute :
- paiements partiels ;
- règlements groupés ;
- plusieurs règlements sur une même facture ;
- allocations manuelles ou proposées ;
- virements internes entre comptes bancaires configurés ;
- opérations spéciales sans invention de compte.

Les montants de rapprochement sont en MAD. Les écarts de change entre date de
facture et date de règlement seront traités par le moteur Devises V2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
import re
import unicodedata
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ecriture import EcritureComptable
from app.models.enums import (
    StatutValidationEnum,
    TypeEcritureEnum,
    TypeMouvementBancaireEnum,
)
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.services import bank_account_service, exchange_difference_service

STATUT_NON_RAPPROCHE = "non_rapproche"
STATUT_PROPOSE = "propose"
STATUT_AUTOMATIQUE = "automatique"
STATUT_CONFIRME = "confirme"
STATUT_AMBIGU = "ambigu"

MODE_SIMPLE = "simple"
MODE_PARTIEL = "partiel"
MODE_GROUPE = "groupe"
MODE_SPECIAL = "special"

STATUTS_ALLOCATION_ACTIFS = {"propose", "automatique", "confirme"}
STATUTS_ALLOCATION_COMPTABILISES = {"automatique", "confirme"}

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
ECART_MONTANT_MAX = Decimal("0.01")
FENETRE_DATE_MAX_JOURS = 180
SEUIL_AUTOMATIQUE = Decimal("90.00")
SEUIL_PARTIEL_PROPOSE = Decimal("65.00")
MAX_CANDIDATS_GROUPE = 12
MAX_FACTURES_GROUPE = 4

_MOTS_IGNORES = {
    "SOCIETE", "STE", "SARL", "SAS", "SA", "SNC", "MAROC", "MAROCAINE",
    "ET", "DE", "DES", "DU", "LA", "LE", "LES", "POUR", "VERS", "VIR",
    "VIREMENT", "RECU", "REGLEMENT", "PAIEMENT", "FACTURE", "FACT",
}


@dataclass(frozen=True)
class CandidatRapprochement:
    ecriture: EcritureComptable
    montant_deja_regle: Decimal
    montant_restant: Decimal
    montant_suggere: Decimal
    type_suggestion: str
    score: Decimal
    raisons: tuple[str, ...]


@dataclass(frozen=True)
class CandidatVirementInterne:
    mouvement: MouvementBancaire
    score: Decimal
    raisons: tuple[str, ...]


def _decimal2(value: object | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _normaliser_texte(value: object | None) -> str:
    text = str(value or "").upper().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def _tokens_tiers(value: object | None) -> set[str]:
    return {
        token for token in _normaliser_texte(value).split()
        if len(token) >= 4 and token not in _MOTS_IGNORES
    }


def type_ecriture_attendu(
    type_mouvement: TypeMouvementBancaireEnum | str,
) -> TypeEcritureEnum:
    value = getattr(type_mouvement, "value", type_mouvement)
    return (
        TypeEcritureEnum.VENTE
        if str(value).lower() == TypeMouvementBancaireEnum.CREDIT.value
        else TypeEcritureEnum.ACHAT
    )


def _allocations_mouvement(
    db: Session,
    mouvement_id: uuid.UUID,
    *,
    statuts: set[str] | None = None,
) -> list[RapprochementBancaireAllocation]:
    query = db.query(RapprochementBancaireAllocation).filter(
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement_id,
    )
    if statuts:
        query = query.filter(RapprochementBancaireAllocation.statut.in_(list(statuts)))
    return query.order_by(RapprochementBancaireAllocation.created_at.asc()).all()


def montant_regle_facture(
    db: Session,
    ecriture_id: uuid.UUID,
    *,
    exclure_mouvement_id: uuid.UUID | None = None,
) -> Decimal:
    valeur_reglee = func.coalesce(
        RapprochementBancaireAllocation.valeur_comptable_mad,
        RapprochementBancaireAllocation.montant_affecte,
    )
    query = db.query(func.coalesce(func.sum(valeur_reglee), 0)).filter(
        RapprochementBancaireAllocation.ecriture_id == ecriture_id,
        RapprochementBancaireAllocation.statut.in_(list(STATUTS_ALLOCATION_COMPTABILISES)),
    )
    if exclure_mouvement_id is not None:
        query = query.filter(
            RapprochementBancaireAllocation.mouvement_bancaire_id != exclure_mouvement_id
        )
    value = query.scalar()
    return _decimal2(value) or ZERO


def montant_restant_facture(
    db: Session,
    ecriture: EcritureComptable,
    *,
    exclure_mouvement_id: uuid.UUID | None = None,
) -> Decimal:
    total = _decimal2(ecriture.montant_ttc) or ZERO
    paid = montant_regle_facture(
        db,
        ecriture.id,
        exclure_mouvement_id=exclure_mouvement_id,
    )
    remaining = total - paid
    return remaining if remaining > ZERO else ZERO


def evaluer_candidat(
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable,
) -> tuple[Decimal, tuple[str, ...]] | None:
    """Compatibilité V1 : évalue uniquement un règlement exact TTC."""
    amount = _decimal2(getattr(mouvement, "montant", None))
    invoice = _decimal2(getattr(ecriture, "montant_ttc", None))
    if amount is None or invoice is None or abs(amount - invoice) > ECART_MONTANT_MAX:
        return None
    if getattr(mouvement, "date_operation", None) and getattr(ecriture, "date_piece", None):
        gap = abs((mouvement.date_operation - ecriture.date_piece).days)
        if gap > FENETRE_DATE_MAX_JOURS:
            return None
    else:
        gap = None
    score = Decimal("70.00")
    reasons = ["Montant TTC identique."]
    if gap is not None:
        if gap <= 7:
            score += Decimal("15.00")
            reasons.append("Date bancaire à moins de 7 jours de la facture.")
        elif gap <= 30:
            score += Decimal("10.00")
            reasons.append("Date bancaire à moins de 30 jours de la facture.")
        elif gap <= 90:
            score += Decimal("5.00")
            reasons.append("Date bancaire à moins de 90 jours de la facture.")
    tokens = _tokens_tiers(getattr(ecriture, "tiers", None))
    bank_tokens = set(_normaliser_texte(getattr(mouvement, "libelle", None)).split())
    if tokens & bank_tokens:
        score += Decimal("15.00")
        reasons.append("Tiers reconnu dans le libellé bancaire.")
    return min(score, Decimal("100.00")), tuple(reasons)


def _score_candidat(
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable,
    montant_restant: Decimal,
) -> tuple[Decimal, tuple[str, ...], str] | None:
    montant_mouvement = _decimal2(mouvement.montant)
    if montant_mouvement is None or montant_mouvement <= ZERO or montant_restant <= ZERO:
        return None

    if mouvement.date_operation and ecriture.date_piece:
        gap = abs((mouvement.date_operation - ecriture.date_piece).days)
        if gap > FENETRE_DATE_MAX_JOURS:
            return None
    else:
        gap = None

    exact = abs(montant_mouvement - montant_restant) <= ECART_MONTANT_MAX
    partial = montant_mouvement < montant_restant
    if exact:
        score = Decimal("70.00")
        reasons = ["Le mouvement correspond exactement au solde restant de la facture."]
        suggestion = MODE_SIMPLE
    elif partial:
        score = Decimal("35.00")
        reasons = ["Le mouvement est inférieur au solde restant : paiement partiel possible."]
        suggestion = MODE_PARTIEL
    else:
        # Un mouvement supérieur à une facture peut faire partie d'un règlement groupé,
        # mais n'est pas un candidat individuel.
        score = Decimal("25.00")
        reasons = ["Le mouvement est supérieur à cette facture : regroupement possible."]
        suggestion = MODE_GROUPE

    if gap is not None:
        if gap <= 7:
            score += Decimal("15.00")
            reasons.append("Date bancaire à moins de 7 jours de la facture.")
        elif gap <= 30:
            score += Decimal("10.00")
            reasons.append("Date bancaire à moins de 30 jours de la facture.")
        elif gap <= 90:
            score += Decimal("5.00")
            reasons.append("Date bancaire à moins de 90 jours de la facture.")

    tokens = _tokens_tiers(ecriture.tiers)
    bank_tokens = set(_normaliser_texte(mouvement.libelle).split())
    common = sorted(tokens & bank_tokens)
    if common:
        score += Decimal("20.00")
        reasons.append("Tiers reconnu dans le libellé bancaire.")

    if score > Decimal("100.00"):
        score = Decimal("100.00")
    return score, tuple(reasons), suggestion


def calculer_candidats(
    db: Session,
    mouvement: MouvementBancaire,
) -> list[CandidatRapprochement]:
    if mouvement.entreprise_id is None or mouvement.nature_operation != "reglement_facture":
        return []

    montant = _decimal2(mouvement.montant)
    if montant is None or montant <= ZERO:
        return []

    expected = type_ecriture_attendu(mouvement.type_mouvement)
    entries = (
        db.query(EcritureComptable)
        .filter(
            EcritureComptable.cabinet_id == mouvement.cabinet_id,
            EcritureComptable.entreprise_id == mouvement.entreprise_id,
            EcritureComptable.type_ecriture == expected,
            EcritureComptable.statut_validation != StatutValidationEnum.REJETE,
        )
        .order_by(EcritureComptable.date_piece.desc().nullslast())
        .all()
    )

    results: list[CandidatRapprochement] = []
    for entry in entries:
        total = _decimal2(entry.montant_ttc)
        if total is None or total <= ZERO:
            continue
        paid = montant_regle_facture(
            db,
            entry.id,
            exclure_mouvement_id=mouvement.id,
        )
        remaining = total - paid
        if remaining <= ZERO:
            continue
        evaluated = _score_candidat(mouvement, entry, remaining)
        if evaluated is None:
            continue
        score, reasons, suggestion = evaluated
        suggested_amount = min(montant, remaining)
        results.append(
            CandidatRapprochement(
                ecriture=entry,
                montant_deja_regle=paid,
                montant_restant=remaining,
                montant_suggere=suggested_amount,
                type_suggestion=suggestion,
                score=score,
                raisons=reasons,
            )
        )

    results.sort(
        key=lambda item: (
            item.score,
            item.ecriture.date_piece or mouvement.date_operation,
        ),
        reverse=True,
    )
    return results


def _clear_proposed_allocations(db: Session, mouvement: MouvementBancaire) -> None:
    db.query(RapprochementBancaireAllocation).filter(
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
        RapprochementBancaireAllocation.statut == "propose",
    ).delete(synchronize_session=False)


def _set_legacy_pointer(db: Session, mouvement: MouvementBancaire) -> None:
    allocations = _allocations_mouvement(
        db,
        mouvement.id,
        statuts=STATUTS_ALLOCATION_ACTIFS,
    )
    mouvement.ecriture_rapprochee_id = allocations[0].ecriture_id if len(allocations) == 1 else None


def _create_or_replace_allocation(
    db: Session,
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable,
    montant_affecte: Decimal,
    *,
    statut: str,
    score: Decimal | None,
    raison: str | None,
    user_id: uuid.UUID | None = None,
) -> RapprochementBancaireAllocation:
    allocation = (
        db.query(RapprochementBancaireAllocation)
        .filter(
            RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
            RapprochementBancaireAllocation.ecriture_id == ecriture.id,
        )
        .one_or_none()
    )
    if allocation is None:
        allocation = RapprochementBancaireAllocation(
            cabinet_id=mouvement.cabinet_id,
            entreprise_id=mouvement.entreprise_id,
            mouvement_bancaire_id=mouvement.id,
            ecriture_id=ecriture.id,
            montant_affecte=montant_affecte,
            statut=statut,
        )
        db.add(allocation)
    else:
        allocation.montant_affecte = montant_affecte
        allocation.statut = statut

    allocation.score = score
    allocation.raison = (raison or None)[:500] if raison else None
    allocation.confirme_par = user_id if statut == "confirme" else None
    allocation.date_confirmation = (
        datetime.now(timezone.utc) if statut in {"automatique", "confirme"} else None
    )
    return allocation


def _find_unique_group(
    mouvement: MouvementBancaire,
    candidates: list[CandidatRapprochement],
) -> list[CandidatRapprochement] | None:
    target = _decimal2(mouvement.montant)
    if target is None:
        return None

    # Priorité aux candidats avec signal tiers/date raisonnable, pour éviter les
    # combinaisons arbitraires sur de gros dossiers.
    pool = [c for c in candidates if c.score >= Decimal("45.00")][:MAX_CANDIDATS_GROUPE]
    found: list[list[CandidatRapprochement]] = []
    for size in range(2, min(MAX_FACTURES_GROUPE, len(pool)) + 1):
        for combo in combinations(pool, size):
            total = sum((c.montant_restant for c in combo), ZERO)
            if abs(total - target) <= ECART_MONTANT_MAX:
                found.append(list(combo))
                if len(found) > 1:
                    return None
    return found[0] if len(found) == 1 else None


def rapprocher_mouvement(
    db: Session,
    mouvement: MouvementBancaire,
) -> list[CandidatRapprochement]:
    """Propose/automatise sans commit. Les confirmations humaines sont préservées."""
    document_data = dict(getattr(getattr(mouvement, "document", None), "donnees_extraites", None) or {})
    bank_account_service.affecter_compte_bancaire_mouvement(
        db,
        mouvement,
        donnees_document=document_data,
    )

    if mouvement.nature_operation != "reglement_facture":
        _clear_proposed_allocations(db, mouvement)
        mouvement.mode_rapprochement = MODE_SPECIAL
        mouvement.ecriture_rapprochee_id = None
        mouvement.statut_rapprochement = STATUT_NON_RAPPROCHE
        mouvement.score_rapprochement = None
        mouvement.raison_rapprochement = "Opération bancaire spéciale : rapprochement facture non appliqué."
        return []

    confirmed = _allocations_mouvement(db, mouvement.id, statuts={"confirme"})
    if confirmed:
        _set_legacy_pointer(db, mouvement)
        total = sum((_decimal2(a.montant_affecte) or ZERO for a in confirmed), ZERO)
        movement_amount = _decimal2(mouvement.montant) or ZERO
        mouvement.statut_rapprochement = STATUT_CONFIRME
        if len(confirmed) > 1:
            mouvement.mode_rapprochement = MODE_GROUPE
        else:
            entry = db.get(EcritureComptable, confirmed[0].ecriture_id)
            invoice_total = _decimal2(entry.montant_ttc) if entry is not None else None
            mouvement.mode_rapprochement = (
                MODE_PARTIEL
                if invoice_total is not None and (_decimal2(confirmed[0].montant_affecte) or ZERO) < invoice_total
                else MODE_SIMPLE
            )
        mouvement.rapprochement_confirme_par = confirmed[0].confirme_par
        mouvement.date_rapprochement = confirmed[0].date_confirmation
        mouvement.raison_rapprochement = "Rapprochement confirmé manuellement."
        return calculer_candidats(db, mouvement)

    _clear_proposed_allocations(db, mouvement)
    # Les allocations automatiques peuvent être recalculées.
    db.query(RapprochementBancaireAllocation).filter(
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
        RapprochementBancaireAllocation.statut == "automatique",
    ).delete(synchronize_session=False)

    candidates = calculer_candidats(db, mouvement)
    exacts = [
        c for c in candidates
        if abs(c.montant_restant - (_decimal2(mouvement.montant) or ZERO)) <= ECART_MONTANT_MAX
    ]

    if len(exacts) == 1 and exacts[0].score >= SEUIL_AUTOMATIQUE:
        candidate = exacts[0]
        _create_or_replace_allocation(
            db,
            mouvement,
            candidate.ecriture,
            candidate.montant_restant,
            statut="automatique",
            score=candidate.score,
            raison=" ".join(candidate.raisons),
        )
        mouvement.statut_rapprochement = STATUT_AUTOMATIQUE
        mouvement.mode_rapprochement = MODE_SIMPLE
        mouvement.score_rapprochement = candidate.score
        mouvement.raison_rapprochement = " ".join(candidate.raisons)[:500]
        mouvement.date_rapprochement = datetime.now(timezone.utc)
        mouvement.rapprochement_confirme_par = None
        _set_legacy_pointer(db, mouvement)
        return candidates

    if len(exacts) > 1:
        mouvement.ecriture_rapprochee_id = None
        mouvement.statut_rapprochement = STATUT_AMBIGU
        mouvement.mode_rapprochement = MODE_SIMPLE
        mouvement.score_rapprochement = max(c.score for c in exacts)
        mouvement.raison_rapprochement = (
            f"{len(exacts)} factures ont exactement le même solde restant. Confirmation manuelle requise."
        )
        return candidates

    group = _find_unique_group(mouvement, candidates)
    if group:
        for candidate in group:
            _create_or_replace_allocation(
                db,
                mouvement,
                candidate.ecriture,
                candidate.montant_restant,
                statut="propose",
                score=candidate.score,
                raison="Règlement groupé proposé. " + " ".join(candidate.raisons),
            )
        mouvement.ecriture_rapprochee_id = None
        mouvement.statut_rapprochement = STATUT_PROPOSE
        mouvement.mode_rapprochement = MODE_GROUPE
        mouvement.score_rapprochement = min(c.score for c in group)
        mouvement.raison_rapprochement = f"Règlement groupé proposé sur {len(group)} factures."
        return candidates

    partials = [
        c for c in candidates
        if c.type_suggestion == MODE_PARTIEL and c.score >= SEUIL_PARTIEL_PROPOSE
    ]
    if len(partials) == 1:
        candidate = partials[0]
        amount = _decimal2(mouvement.montant) or ZERO
        _create_or_replace_allocation(
            db,
            mouvement,
            candidate.ecriture,
            amount,
            statut="propose",
            score=candidate.score,
            raison="Paiement partiel proposé. " + " ".join(candidate.raisons),
        )
        mouvement.statut_rapprochement = STATUT_PROPOSE
        mouvement.mode_rapprochement = MODE_PARTIEL
        mouvement.score_rapprochement = candidate.score
        mouvement.raison_rapprochement = "Paiement partiel proposé ; confirmation requise."
        _set_legacy_pointer(db, mouvement)
        return candidates

    mouvement.ecriture_rapprochee_id = None
    mouvement.statut_rapprochement = STATUT_NON_RAPPROCHE if not candidates else STATUT_AMBIGU
    mouvement.mode_rapprochement = MODE_SIMPLE
    mouvement.score_rapprochement = candidates[0].score if candidates else None
    mouvement.raison_rapprochement = (
        "Aucune facture compatible trouvée."
        if not candidates
        else "Plusieurs possibilités existent ; utilisez l'affectation manuelle."
    )
    mouvement.rapprochement_confirme_par = None
    mouvement.date_rapprochement = None
    return candidates


def confirmer_allocations(
    db: Session,
    mouvement: MouvementBancaire,
    allocations: list[
        tuple[EcritureComptable, Decimal]
        | tuple[EcritureComptable, Decimal, Decimal | None]
    ],
    user_id: uuid.UUID,
) -> None:
    if mouvement.nature_operation != "reglement_facture":
        raise ValueError("Cette opération n'est pas configurée comme règlement de facture.")
    if not allocations:
        raise ValueError("Au moins une affectation est obligatoire.")

    movement_amount = _decimal2(mouvement.montant)
    if movement_amount is None or movement_amount <= ZERO:
        raise ValueError("Montant bancaire invalide.")

    normalized_allocations: list[tuple[EcritureComptable, Decimal, Decimal | None, exchange_difference_service.EcartChangeResultat]] = []
    total_allocated = ZERO
    for item in allocations:
        entry, amount_raw = item[0], item[1]
        devise_raw = item[2] if len(item) > 2 else None
        amount = _decimal2(amount_raw)
        if amount is None or amount <= ZERO:
            raise ValueError("Chaque montant affecté doit être strictement positif.")
        if entry.cabinet_id != mouvement.cabinet_id or entry.entreprise_id != mouvement.entreprise_id:
            raise ValueError("Une facture n'appartient pas à la même entreprise.")
        if entry.type_ecriture != type_ecriture_attendu(mouvement.type_mouvement):
            raise ValueError("Le sens d'une facture est incompatible avec le mouvement bancaire.")
        remaining = montant_restant_facture(
            db,
            entry,
            exclure_mouvement_id=mouvement.id,
        )
        fx_result = exchange_difference_service.preparer_ecart_allocation(
            db,
            mouvement=mouvement,
            ecriture=entry,
            montant_reglement_mad=amount,
            montant_devise_affecte=devise_raw,
        )
        valeur_imputee = fx_result.valeur_comptable_mad or amount
        if valeur_imputee - remaining > ECART_MONTANT_MAX:
            raise ValueError(
                f"La valeur comptable affectée à {entry.numero_piece or entry.id} dépasse son solde restant ({remaining})."
            )
        total_allocated += amount
        normalized_allocations.append((entry, amount, devise_raw, fx_result))

    if abs(total_allocated - movement_amount) > ECART_MONTANT_MAX:
        raise ValueError(
            "Le total affecté doit couvrir exactement le mouvement bancaire. "
            "Pour un paiement partiel, affectez tout le mouvement à une partie du solde de la facture."
        )

    # Une confirmation remplace toute proposition/auto précédente de ce mouvement.
    db.query(RapprochementBancaireAllocation).filter(
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
    ).delete(synchronize_session=False)
    db.flush()

    now = datetime.now(timezone.utc)
    has_exchange_review = False
    review_reasons: list[str] = []
    for entry, amount, _devise_raw, fx_result in normalized_allocations:
        allocation = _create_or_replace_allocation(
            db,
            mouvement,
            entry,
            amount,
            statut="confirme",
            score=Decimal("100.00"),
            raison="Affectation confirmée manuellement.",
            user_id=user_id,
        )
        allocation.date_confirmation = now
        exchange_difference_service.appliquer_resultat_allocation(allocation, fx_result)
        if not fx_result.complet:
            has_exchange_review = True
            if fx_result.raison:
                review_reasons.append(fx_result.raison)

    mouvement.statut_rapprochement = STATUT_CONFIRME
    if len(allocations) > 1:
        mouvement.mode_rapprochement = MODE_GROUPE
    else:
        only_entry, only_amount, _devise_raw, _fx_result = normalized_allocations[0]
        invoice_total = _decimal2(only_entry.montant_ttc) or ZERO
        mouvement.mode_rapprochement = (
            MODE_PARTIEL if (_decimal2(only_amount) or ZERO) < invoice_total else MODE_SIMPLE
        )
    mouvement.score_rapprochement = Decimal("100.00")
    mouvement.raison_rapprochement = (
        "Affectation confirmée manuellement."
        if total_allocated == movement_amount
        else f"Affectation partielle confirmée : {total_allocated} MAD sur {movement_amount} MAD."
    )
    mouvement.rapprochement_confirme_par = user_id
    mouvement.date_rapprochement = now
    _set_legacy_pointer(db, mouvement)
    if has_exchange_review:
        mouvement.statut_rapprochement = "a_verifier"
        mouvement.raison_rapprochement = (
            "Écart de change à vérifier : " + " | ".join(dict.fromkeys(review_reasons))
        )[:500]


def confirmer_rapprochement(
    db: Session,
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable,
    user_id: uuid.UUID,
) -> None:
    amount = min(
        _decimal2(mouvement.montant) or ZERO,
        montant_restant_facture(db, ecriture, exclure_mouvement_id=mouvement.id),
    )
    confirmer_allocations(db, mouvement, [(ecriture, amount)], user_id)


def annuler_rapprochement(db: Session, mouvement: MouvementBancaire) -> None:
    db.query(RapprochementBancaireAllocation).filter(
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
    ).delete(synchronize_session=False)
    mouvement.ecriture_rapprochee_id = None
    mouvement.statut_rapprochement = STATUT_NON_RAPPROCHE
    mouvement.mode_rapprochement = MODE_SIMPLE
    mouvement.score_rapprochement = None
    mouvement.raison_rapprochement = "Rapprochement annulé manuellement."
    mouvement.rapprochement_confirme_par = None
    mouvement.date_rapprochement = None


def calculer_candidats_virement_interne(
    db: Session,
    mouvement: MouvementBancaire,
) -> list[CandidatVirementInterne]:
    amount = _decimal2(mouvement.montant)
    if amount is None or amount <= ZERO:
        return []
    opposite = (
        TypeMouvementBancaireEnum.CREDIT
        if getattr(mouvement.type_mouvement, "value", mouvement.type_mouvement) == TypeMouvementBancaireEnum.DEBIT.value
        else TypeMouvementBancaireEnum.DEBIT
    )
    rows = (
        db.query(MouvementBancaire)
        .filter(
            MouvementBancaire.cabinet_id == mouvement.cabinet_id,
            MouvementBancaire.entreprise_id == mouvement.entreprise_id,
            MouvementBancaire.id != mouvement.id,
            MouvementBancaire.type_mouvement == opposite,
            MouvementBancaire.montant.between(amount - ECART_MONTANT_MAX, amount + ECART_MONTANT_MAX),
            MouvementBancaire.mouvement_lie_id.is_(None),
        )
        .all()
    )
    results: list[CandidatVirementInterne] = []
    for row in rows:
        gap = abs((row.date_operation - mouvement.date_operation).days)
        if gap > 3:
            continue
        if row.compte_banque and mouvement.compte_banque and row.compte_banque == mouvement.compte_banque:
            continue
        score = Decimal("80.00")
        reasons = ["Montant opposé identique."]
        if gap == 0:
            score += Decimal("15.00")
            reasons.append("Même date.")
        else:
            score += Decimal("10.00")
            reasons.append("Date à moins de 3 jours.")
        if row.compte_banque and mouvement.compte_banque and row.compte_banque != mouvement.compte_banque:
            score += Decimal("5.00")
            reasons.append("Deux comptes bancaires distincts.")
        results.append(CandidatVirementInterne(row, min(score, Decimal("100.00")), tuple(reasons)))
    results.sort(key=lambda item: item.score, reverse=True)
    return results


def lier_virement_interne(
    db: Session,
    mouvement: MouvementBancaire,
    autre: MouvementBancaire,
) -> None:
    if mouvement.cabinet_id != autre.cabinet_id or mouvement.entreprise_id != autre.entreprise_id:
        raise ValueError("Les deux mouvements doivent appartenir à la même entreprise.")
    if mouvement.id == autre.id:
        raise ValueError("Un mouvement ne peut pas être lié à lui-même.")
    if _decimal2(mouvement.montant) != _decimal2(autre.montant):
        raise ValueError("Les montants des deux mouvements doivent être identiques.")
    if mouvement.type_mouvement == autre.type_mouvement:
        raise ValueError("Un virement interne nécessite un débit et un crédit.")
    if abs((mouvement.date_operation - autre.date_operation).days) > 3:
        raise ValueError("Les dates sont trop éloignées pour un virement interne automatique.")
    if not mouvement.compte_banque or not autre.compte_banque:
        raise ValueError("Les deux comptes bancaires exacts doivent être configurés.")
    if mouvement.compte_banque == autre.compte_banque:
        raise ValueError("Les deux mouvements utilisent le même compte bancaire.")

    for item in (mouvement, autre):
        annuler_rapprochement(db, item)
        item.nature_operation = "virement_interne"
        item.mode_rapprochement = MODE_SPECIAL
    mouvement.mouvement_lie_id = autre.id
    autre.mouvement_lie_id = mouvement.id
    mouvement.raison_rapprochement = "Virement interne lié à l'autre compte bancaire."
    autre.raison_rapprochement = "Virement interne lié à l'autre compte bancaire."
