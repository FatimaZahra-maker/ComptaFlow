"""Moteur prudent des regularisations de cloture V1."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.ligne_comptable import LigneComptable
from app.models.regularisation_cloture import RegularisationCloture
from app.services.plan_comptable_service import normaliser_numero_compte
from app.services.cpc_service import calculer_cpc

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
TYPES_REGULARISATION = {
    "amortissement", "provision", "stock", "charge_constatee_avance",
    "produit_constate_avance", "charge_a_payer", "produit_a_recevoir",
    "ajustement_manuel", "resultat_cloture", "report_a_nouveau",
}


@dataclass(frozen=True)
class ValidationCloture:
    valide: bool
    anomalies: tuple[str, ...]


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ZERO


def verifier_configuration(reg: RegularisationCloture) -> ValidationCloture:
    anomalies: list[str] = []
    if reg.type_regularisation not in TYPES_REGULARISATION:
        anomalies.append("Type de regularisation non pris en charge.")
    if _money(reg.montant) <= ZERO:
        anomalies.append("Le montant explicite doit etre strictement positif.")
    if reg.date_ecriture.year != reg.exercice:
        anomalies.append("La date d'ecriture n'appartient pas a l'exercice.")
    if reg.a_extourner and reg.date_extourne is None:
        anomalies.append("La date d'extourne doit etre explicitement configuree.")
    if reg.type_regularisation == "amortissement":
        requis = {"valeur_amortissable", "date_mise_service", "methode", "cumul_anterieur", "dotation_exercice"}
        absents = sorted(cle for cle in requis if reg.donnees_calcul.get(cle) in (None, ""))
        if not (reg.donnees_calcul.get("duree_mois") or reg.donnees_calcul.get("taux")):
            absents.append("duree_mois_ou_taux")
        if absents:
            anomalies.append("Configuration d'amortissement incomplete: " + ", ".join(absents) + ".")
        elif _money(reg.donnees_calcul.get("dotation_exercice")) != _money(reg.montant):
            anomalies.append("Le montant doit correspondre a la dotation d'exercice explicitement fournie.")
    if reg.type_regularisation == "provision" and reg.donnees_calcul.get("operation") not in {
        "constitution", "augmentation", "reprise"
    }:
        anomalies.append("L'operation de provision doit etre explicite: constitution, augmentation ou reprise.")
    if reg.type_regularisation == "report_a_nouveau" and reg.report_source_id is None:
        anomalies.append("Le report a nouveau doit referencer son exercice source.")
    return ValidationCloture(not anomalies, tuple(anomalies))


def construire_lignes_equilibrees(reg: RegularisationCloture) -> list[dict]:
    debit = normaliser_numero_compte(reg.compte_debit)
    credit = normaliser_numero_compte(reg.compte_credit)
    montant = _money(reg.montant)
    if not debit or not credit:
        raise ValueError("Les comptes debit et credit exacts sont obligatoires.")
    if debit == credit:
        raise ValueError("Les comptes debit et credit doivent etre distincts.")
    if montant <= ZERO:
        raise ValueError("Le montant doit etre strictement positif.")
    commun = {
        "date_ecriture": reg.date_ecriture, "journal": "OD",
        "numero_piece": f"CLOT-{reg.exercice}-{str(reg.id)[:8]}",
        "libelle": reg.libelle, "origine": "cloture", "est_validee": True,
    }
    return [
        {**commun, "compte": debit, "debit": montant, "credit": ZERO, "ordre": 1},
        {**commun, "compte": credit, "debit": ZERO, "credit": montant, "ordre": 2},
    ]


def verifier_scope(reg: RegularisationCloture, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> None:
    if reg.cabinet_id != cabinet_id or reg.entreprise_id != entreprise_id:
        raise ValueError("Regularisation hors du cabinet ou de l'entreprise demandes.")


def verifier_comptes_dans_plan(reg: RegularisationCloture, comptes_actifs: set[str]) -> ValidationCloture:
    debit = normaliser_numero_compte(reg.compte_debit)
    credit = normaliser_numero_compte(reg.compte_credit)
    anomalies: list[str] = []
    if not debit or not credit or debit == credit:
        anomalies.append("Deux comptes exacts et distincts sont requis.")
    else:
        manquants = sorted({debit, credit} - comptes_actifs)
        if manquants:
            anomalies.append("Compte(s) absent(s) ou inactif(s) dans le plan de l'entreprise: " + ", ".join(manquants) + ".")
    return ValidationCloture(not anomalies, tuple(anomalies))


def verifier_report_source(
    reg: RegularisationCloture,
    source: RegularisationCloture | None,
    deja_utilise: bool,
) -> ValidationCloture:
    anomalies: list[str] = []
    if source is None or source.cabinet_id != reg.cabinet_id or source.entreprise_id != reg.entreprise_id:
        anomalies.append("La source du report est absente ou hors tenant.")
    elif source.exercice != reg.exercice - 1 or source.type_regularisation != "resultat_cloture" or source.statut != "comptabilisee":
        anomalies.append("La source du report n'est pas une cloture comptabilisee de l'exercice precedent.")
    elif _money(source.montant) != _money(reg.montant):
        anomalies.append("Le montant du report differe de sa source de cloture.")
    if deja_utilise:
        anomalies.append("Cette source a deja ete utilisee pour un report a nouveau.")
    return ValidationCloture(not anomalies, tuple(anomalies))


def _comptes_exacts(db: Session, reg: RegularisationCloture) -> tuple[set[str], list[str]]:
    demandes = {normaliser_numero_compte(reg.compte_debit), normaliser_numero_compte(reg.compte_credit)}
    demandes.discard(None)
    if len(demandes) != 2:
        return set(), ["Deux comptes exacts et distincts sont requis."]
    trouves = set(db.execute(
        select(CompteComptableEntreprise.numero_compte).where(
            CompteComptableEntreprise.cabinet_id == reg.cabinet_id,
            CompteComptableEntreprise.entreprise_id == reg.entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
            CompteComptableEntreprise.numero_compte.in_(demandes),
        )
    ).scalars().all())
    controle = verifier_comptes_dans_plan(reg, trouves)
    return trouves, list(controle.anomalies)


def valider_regularisation(db: Session, reg: RegularisationCloture, user_id: uuid.UUID) -> RegularisationCloture:
    controle = verifier_configuration(reg)
    _, anomalies_comptes = _comptes_exacts(db, reg)
    anomalies = list(controle.anomalies) + anomalies_comptes
    if reg.type_regularisation == "resultat_cloture":
        cpc = calculer_cpc(
            db, cabinet_id=reg.cabinet_id, entreprise_id=reg.entreprise_id, annee=reg.exercice
        )
        if cpc.a_verifier:
            anomalies.append("Le resultat CPC courant comporte des anomalies et ne peut pas fonder la cloture.")
        elif _money(reg.montant) != abs(_money(cpc.resultat_net)):
            anomalies.append("Le montant ne correspond pas au resultat net issu des lignes comptables validees.")
    if reg.type_regularisation == "report_a_nouveau" and reg.report_source_id:
        source = db.execute(select(RegularisationCloture).where(
            RegularisationCloture.id == reg.report_source_id,
            RegularisationCloture.cabinet_id == reg.cabinet_id,
            RegularisationCloture.entreprise_id == reg.entreprise_id,
            RegularisationCloture.exercice == reg.exercice - 1,
            RegularisationCloture.type_regularisation == "resultat_cloture",
            RegularisationCloture.statut == "comptabilisee",
        )).scalar_one_or_none()
        doublon = db.execute(select(RegularisationCloture.id).where(
            RegularisationCloture.report_source_id == reg.report_source_id,
            RegularisationCloture.id != reg.id,
        )).scalar_one_or_none()
        anomalies.extend(verifier_report_source(reg, source, doublon is not None).anomalies)
    reg.anomalies = anomalies
    reg.statut = "a_verifier" if anomalies else "validee"
    reg.validated_by = user_id if not anomalies else None
    reg.validated_at = datetime.now(timezone.utc) if not anomalies else None
    return reg


def generer_lignes(db: Session, reg: RegularisationCloture) -> list[LigneComptable]:
    if reg.statut == "comptabilisee":
        return db.execute(select(LigneComptable).where(
            LigneComptable.cabinet_id == reg.cabinet_id,
            LigneComptable.entreprise_id == reg.entreprise_id,
            LigneComptable.regularisation_cloture_id == reg.id,
        ).order_by(LigneComptable.ordre)).scalars().all()
    if reg.statut != "validee":
        raise ValueError("Seule une regularisation validee peut etre comptabilisee.")
    _, anomalies = _comptes_exacts(db, reg)
    if anomalies:
        reg.anomalies = anomalies
        reg.statut = "a_verifier"
        raise ValueError(anomalies[0])
    lignes = [LigneComptable(
        cabinet_id=reg.cabinet_id, entreprise_id=reg.entreprise_id,
        regularisation_cloture_id=reg.id, ecriture_id=None, mouvement_bancaire_id=None, **item
    ) for item in construire_lignes_equilibrees(reg)]
    db.add_all(lignes)
    reg.statut = "comptabilisee"
    reg.generated_at = datetime.now(timezone.utc)
    return lignes


def annuler_regularisation(db: Session, reg: RegularisationCloture, motif: str) -> None:
    if reg.statut == "annulee":
        return
    lignes = db.execute(select(LigneComptable).where(
        LigneComptable.cabinet_id == reg.cabinet_id,
        LigneComptable.entreprise_id == reg.entreprise_id,
        LigneComptable.regularisation_cloture_id == reg.id,
    )).scalars().all()
    for ligne in lignes:
        ligne.est_validee = False
    reg.statut = "annulee"
    reg.motif_annulation = motif
