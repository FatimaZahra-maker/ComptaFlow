"""Résolution des comptes bancaires configurés par entreprise."""
from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy.orm import Session

from app.models.compte_bancaire_entreprise import CompteBancaireEntreprise
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.mouvement_bancaire import MouvementBancaire
from app.services import plan_comptable_service


def normaliser_identifiant(value: object | None) -> str:
    text = str(value or "").upper().strip()
    return re.sub(r"[^A-Z0-9]", "", text)


def normaliser_nom(value: object | None) -> str:
    text = str(value or "").upper().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split())


def valider_compte_comptable_banque(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    numero_compte: str,
) -> CompteComptableEntreprise:
    compte = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.numero_compte == numero_compte.strip(),
            CompteComptableEntreprise.is_active.is_(True),
        )
        .one_or_none()
    )
    if compte is None:
        raise ValueError(
            "Le compte bancaire exact doit déjà exister dans le plan comptable de l'entreprise."
        )
    if compte.type_usage not in {"banque", "autre"}:
        raise ValueError(
            "Le compte choisi n'est pas configuré comme compte bancaire dans le plan comptable."
        )
    return compte


def identifier_compte_bancaire(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    rib: object | None = None,
    iban: object | None = None,
    banque_nom: object | None = None,
) -> CompteBancaireEntreprise | None:
    comptes = (
        db.query(CompteBancaireEntreprise)
        .filter(
            CompteBancaireEntreprise.cabinet_id == cabinet_id,
            CompteBancaireEntreprise.entreprise_id == entreprise_id,
            CompteBancaireEntreprise.is_active.is_(True),
        )
        .all()
    )
    if not comptes:
        return None

    identifiants = {
        value for value in (
            normaliser_identifiant(rib),
            normaliser_identifiant(iban),
        ) if value
    }
    if identifiants:
        exacts = []
        for compte in comptes:
            connus = {
                value for value in (
                    normaliser_identifiant(compte.rib),
                    normaliser_identifiant(compte.iban),
                ) if value
            }
            if identifiants & connus:
                exacts.append(compte)
        if len(exacts) == 1:
            return exacts[0]
        if len(exacts) > 1:
            return None

    banque = normaliser_nom(banque_nom)
    if banque:
        matches = [
            compte for compte in comptes
            if normaliser_nom(compte.banque_nom) == banque
        ]
        if len(matches) == 1:
            return matches[0]

    # Un seul compte bancaire actif est non ambigu.
    if len(comptes) == 1:
        return comptes[0]
    return None


def affecter_compte_bancaire_mouvement(
    db: Session,
    mouvement: MouvementBancaire,
    *,
    donnees_document: dict | None = None,
) -> None:
    data = donnees_document or {}
    compte = identifier_compte_bancaire(
        db,
        cabinet_id=mouvement.cabinet_id,
        entreprise_id=mouvement.entreprise_id,
        rib=data.get("rib"),
        iban=data.get("iban"),
        banque_nom=data.get("banque"),
    )
    if compte is not None:
        mouvement.compte_bancaire_entreprise_id = compte.id
        mouvement.compte_banque = compte.numero_compte_comptable
        return

    # Compatibilité avec Banque V1 : si un seul compte type_usage=banque existe
    # dans le plan, il reste exploitable sans fabriquer de RIB.
    resolution = plan_comptable_service.chercher_compte_usage_unique(
        db,
        cabinet_id=mouvement.cabinet_id,
        entreprise_id=mouvement.entreprise_id,
        type_usage="banque",
    )
    mouvement.compte_banque = resolution.compte
