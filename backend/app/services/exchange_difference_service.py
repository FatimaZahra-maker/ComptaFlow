"""Devises V2 : calcul et qualification des écarts au règlement.

La valeur du tiers est reprise au cours de la facture. La banque est reprise
pour le montant MAD réellement débité/crédité. L'écart est donc le seul solde
à porter sur un compte de gain ou de perte de change exact du plan entreprise.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.ecriture import EcritureComptable
from app.models.enums import TypeEcritureEnum
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.services import plan_comptable_service

MONEY = Decimal("0.01")
QUANTITY = Decimal("0.000001")
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class EcartChangeResultat:
    applicable: bool
    complet: bool
    valeur_comptable_mad: Decimal | None = None
    montant_reglement_mad: Decimal | None = None
    montant_devise_affecte: Decimal | None = None
    ecart_change_mad: Decimal | None = None
    nature: str | None = None
    compte: str | None = None
    raison: str | None = None


def _decimal(value: object | None, quantum: Decimal) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def calculer_valeur_comptable_partielle(
    *,
    montant_total_devise: Decimal,
    valeur_totale_mad: Decimal,
    montant_devise_regle: Decimal,
) -> Decimal:
    """Prorata de la valeur initiale, sans reconvertir au cours du règlement."""
    total_devise = _decimal(montant_total_devise, QUANTITY)
    total_mad = _decimal(valeur_totale_mad, MONEY)
    regle = _decimal(montant_devise_regle, QUANTITY)
    if total_devise is None or total_devise <= 0:
        raise ValueError("Montant total en devise invalide.")
    if total_mad is None or total_mad < 0:
        raise ValueError("Valeur comptable initiale MAD invalide.")
    if regle is None or regle <= 0 or regle - total_devise > QUANTITY:
        raise ValueError("Montant réglé en devise invalide ou supérieur à la facture.")
    return (total_mad * regle / total_devise).quantize(MONEY, rounding=ROUND_HALF_UP)


def classifier_ecart_change(
    *,
    type_ecriture: TypeEcritureEnum | str,
    valeur_comptable_mad: Decimal,
    montant_reglement_mad: Decimal,
) -> tuple[Decimal, str]:
    """Déduit gain/perte du sens Débit/Crédit, sans table de règle arbitraire.

    Achat : fournisseur débité à la valeur initiale et banque créditée au réel.
    Un règlement supérieur crée donc un débit (perte), un règlement inférieur
    un crédit (gain). Vente : banque débitée au réel et client crédité à la
    valeur initiale ; le classement est donc exactement inverse.
    """
    initial = _decimal(valeur_comptable_mad, MONEY)
    settlement = _decimal(montant_reglement_mad, MONEY)
    if initial is None or settlement is None:
        raise ValueError("Valeurs MAD invalides pour calculer l'écart de change.")
    difference = (settlement - initial).quantize(MONEY)
    if abs(difference) < MONEY:
        return ZERO, "sans_ecart"

    kind = getattr(type_ecriture, "value", type_ecriture)
    if str(kind).lower() == TypeEcritureEnum.ACHAT.value:
        nature = "perte" if difference > 0 else "gain"
    elif str(kind).lower() == TypeEcritureEnum.VENTE.value:
        nature = "gain" if difference > 0 else "perte"
    else:
        raise ValueError("Type d'écriture incompatible avec un écart de change.")
    return abs(difference), nature


def _a_verifier(reason: str) -> EcartChangeResultat:
    return EcartChangeResultat(
        applicable=True,
        complet=False,
        nature="a_verifier",
        raison=reason,
    )


def preparer_ecart_allocation(
    db: Session,
    *,
    mouvement: MouvementBancaire,
    ecriture: EcritureComptable,
    montant_reglement_mad: Decimal,
    montant_devise_affecte: Decimal | None = None,
) -> EcartChangeResultat:
    """Calcule une allocation V2 et résout le compte exact, sans le créer."""
    if (
        mouvement.cabinet_id != ecriture.cabinet_id
        or mouvement.entreprise_id != ecriture.entreprise_id
    ):
        return _a_verifier("Mouvement et facture n'appartiennent pas au même tenant.")

    devise_facture = str(getattr(ecriture, "devise_originale", None) or "MAD").upper()
    devise_reglement = str(getattr(mouvement, "devise_originale", None) or "MAD").upper()
    settlement = _decimal(montant_reglement_mad, MONEY)
    if settlement is None or settlement <= 0:
        return _a_verifier("Montant MAD réel du règlement absent ou invalide.")

    if devise_facture == "MAD":
        return EcartChangeResultat(
            applicable=False,
            complet=True,
            valeur_comptable_mad=settlement,
            montant_reglement_mad=settlement,
            ecart_change_mad=ZERO,
            nature="sans_ecart",
        )
    if devise_reglement != devise_facture:
        return _a_verifier(
            f"Devise facture {devise_facture} incompatible avec le règlement {devise_reglement}."
        )

    total_devise = _decimal(getattr(ecriture, "montant_ttc_devise", None), QUANTITY)
    total_initial = _decimal(
        getattr(ecriture, "montant_ttc_mad", None) or ecriture.montant_ttc,
        MONEY,
    )
    if total_devise is None or total_devise <= 0 or total_initial is None:
        return _a_verifier("Valeur initiale en devise/MAD absente sur la facture.")
    if not getattr(ecriture, "date_cours_initial", None) or not getattr(ecriture, "source_cours_initial", None):
        return _a_verifier("Cours BAM initial de la facture absent ou non traçable.")

    source_reglement = str(getattr(mouvement, "montant_mad_source", None) or "")
    if source_reglement not in {"banque", "bam"}:
        return _a_verifier("Cours BAM du règlement indisponible et aucun montant MAD réel fourni par la banque.")
    if getattr(mouvement, "taux_change", None) is None or getattr(mouvement, "date_cours_change", None) is None:
        return _a_verifier("Cours BAM applicable à la date du règlement absent.")

    devise_part = _decimal(montant_devise_affecte, QUANTITY)
    if devise_part is None:
        mouvement_devise = _decimal(getattr(mouvement, "montant_devise", None), QUANTITY)
        mouvement_mad = _decimal(getattr(mouvement, "montant", None), MONEY)
        if mouvement_devise is None or mouvement_devise <= 0 or mouvement_mad is None or mouvement_mad <= 0:
            return _a_verifier("Montant en devise du règlement absent ; prorata impossible.")
        devise_part = (mouvement_devise * settlement / mouvement_mad).quantize(
            QUANTITY, rounding=ROUND_HALF_UP
        )

    try:
        initial_part = calculer_valeur_comptable_partielle(
            montant_total_devise=total_devise,
            valeur_totale_mad=total_initial,
            montant_devise_regle=devise_part,
        )
        ecart, nature = classifier_ecart_change(
            type_ecriture=ecriture.type_ecriture,
            valeur_comptable_mad=initial_part,
            montant_reglement_mad=settlement,
        )
    except ValueError as exc:
        return _a_verifier(str(exc))

    if nature == "sans_ecart":
        return EcartChangeResultat(
            applicable=True,
            complet=True,
            valeur_comptable_mad=initial_part,
            montant_reglement_mad=settlement,
            montant_devise_affecte=devise_part,
            ecart_change_mad=ZERO,
            nature=nature,
        )

    usage = "gain_change" if nature == "gain" else "perte_change"
    resolution = plan_comptable_service.chercher_compte_usage_unique(
        db,
        cabinet_id=mouvement.cabinet_id,
        entreprise_id=mouvement.entreprise_id,
        type_usage=usage,
    )
    if resolution.compte is None:
        return EcartChangeResultat(
            applicable=True,
            complet=False,
            valeur_comptable_mad=initial_part,
            montant_reglement_mad=settlement,
            montant_devise_affecte=devise_part,
            ecart_change_mad=ecart,
            nature="a_verifier",
            raison=(
                f"Compte exact {usage} {resolution.statut} dans le plan de l'entreprise ; "
                "aucun compte ne sera inventé."
            ),
        )
    return EcartChangeResultat(
        applicable=True,
        complet=True,
        valeur_comptable_mad=initial_part,
        montant_reglement_mad=settlement,
        montant_devise_affecte=devise_part,
        ecart_change_mad=ecart,
        nature=nature,
        compte=resolution.compte,
    )


def appliquer_resultat_allocation(
    allocation: RapprochementBancaireAllocation,
    resultat: EcartChangeResultat,
) -> None:
    allocation.montant_devise_affecte = resultat.montant_devise_affecte
    allocation.valeur_comptable_mad = resultat.valeur_comptable_mad
    allocation.montant_reglement_mad = resultat.montant_reglement_mad
    allocation.ecart_change_mad = resultat.ecart_change_mad
    allocation.nature_ecart_change = resultat.nature
    allocation.compte_ecart_change = resultat.compte
    allocation.statut_ecart_change = (
        "comptabilise" if resultat.complet and resultat.nature not in {None, "sans_ecart"}
        else "non_requis" if resultat.complet
        else "a_verifier"
    )
    allocation.raison_ecart_change = resultat.raison
