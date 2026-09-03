"""Entreprises gérées disponibles dans chaque contexte comptable.

Le filtrage est effectué en base avec des ``EXISTS`` corrélés. Une entreprise
auto-créée depuis un tiers, une banque ou un document OCR n'est jamais proposée
comme dossier géré. Toutes les branches portent simultanément ``cabinet_id`` et
``entreprise_id`` ; aucune donnée d'un autre tenant ne peut rendre une entreprise
disponible.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.compte_bancaire_entreprise import CompteBancaireEntreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import (
    CategorieDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
)
from app.models.ligne_comptable import LigneComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.regularisation_cloture import RegularisationCloture
from app.models.tva_periode import TvaPeriode

ModuleEntreprise = Literal[
    "achats", "ventes", "banque", "comptes_bancaires", "ecritures",
    "registres", "ledger", "balance", "tva", "cloture", "cpc", "bilan",
    "controls",
]

MODULES_AVEC_EXERCICE = {"tva", "cloture", "cpc", "bilan", "controls"}
STATUTS_REGISTRE_SELECTEUR = (
    StatutValidationEnum.BROUILLON,
    StatutValidationEnum.A_VERIFIER,
    StatutValidationEnum.VALIDE,
)


@dataclass(slots=True)
class EntrepriseDisponible:
    id: uuid.UUID
    nom: str
    ice: str | None
    is_active: bool
    creee_automatiquement: bool
    ecritures_brouillon: int = 0
    ecritures_a_verifier: int = 0
    ecritures_validees: int = 0


def _periode(exercice: int) -> tuple[date, date]:
    return date(exercice, 1, 1), date(exercice, 12, 31)


def _exists_document(cabinet_id: uuid.UUID, *criteria):
    return exists(select(1).select_from(Document).where(
        Document.cabinet_id == cabinet_id,
        Document.entreprise_id == Entreprise.id,
        *criteria,
    ))


def _exists_entry(cabinet_id: uuid.UUID, *criteria):
    return exists(select(1).select_from(EcritureComptable).where(
        EcritureComptable.cabinet_id == cabinet_id,
        EcritureComptable.entreprise_id == Entreprise.id,
        *criteria,
    ))


def _exists_line(cabinet_id: uuid.UUID, *criteria):
    return exists(select(1).select_from(LigneComptable).where(
        LigneComptable.cabinet_id == cabinet_id,
        LigneComptable.entreprise_id == Entreprise.id,
        *criteria,
    ))


def construire_requete(
    *,
    cabinet_id: uuid.UUID,
    module: ModuleEntreprise,
    exercice: int | None = None,
):
    if module in MODULES_AVEC_EXERCICE and exercice is None:
        raise ValueError("L'exercice est obligatoire pour ce module.")

    condition = None
    if module == "achats":
        condition = or_(
            _exists_entry(cabinet_id, EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT),
            _exists_document(cabinet_id, Document.categorie.in_([
                CategorieDocumentEnum.ACHATS, CategorieDocumentEnum.FOURNISSEURS,
            ])),
        )
    elif module == "ventes":
        condition = or_(
            _exists_entry(cabinet_id, EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE),
            _exists_document(cabinet_id, Document.categorie.in_([
                CategorieDocumentEnum.VENTES, CategorieDocumentEnum.CLIENTS,
            ])),
        )
    elif module == "banque":
        condition = or_(
            _exists_document(cabinet_id, Document.categorie == CategorieDocumentEnum.BANQUE),
            exists(select(1).select_from(MouvementBancaire).where(
                MouvementBancaire.cabinet_id == cabinet_id,
                MouvementBancaire.entreprise_id == Entreprise.id,
            )),
        )
    elif module == "comptes_bancaires":
        condition = or_(
            exists(select(1).select_from(CompteBancaireEntreprise).where(
                CompteBancaireEntreprise.cabinet_id == cabinet_id,
                CompteBancaireEntreprise.entreprise_id == Entreprise.id,
            )),
            _exists_document(cabinet_id, Document.categorie == CategorieDocumentEnum.BANQUE),
            exists(select(1).select_from(MouvementBancaire).where(
                MouvementBancaire.cabinet_id == cabinet_id,
                MouvementBancaire.entreprise_id == Entreprise.id,
            )),
        )
    elif module == "ecritures":
        condition = _exists_entry(cabinet_id)
    elif module == "registres":
        condition = _exists_entry(
            cabinet_id,
            EcritureComptable.statut_validation.in_(STATUTS_REGISTRE_SELECTEUR),
        )
    elif module in {"ledger", "balance"}:
        condition = _exists_line(cabinet_id)
    elif module == "tva":
        start, end = _periode(exercice)  # type: ignore[arg-type]
        condition = or_(
            exists(select(1).select_from(TvaPeriode).where(
                TvaPeriode.cabinet_id == cabinet_id,
                TvaPeriode.entreprise_id == Entreprise.id,
                TvaPeriode.annee == exercice,
            )),
            _exists_entry(
                cabinet_id,
                EcritureComptable.date_piece >= start,
                EcritureComptable.date_piece <= end,
                EcritureComptable.montant_tva > 0,
            ),
            _exists_line(
                cabinet_id,
                LigneComptable.date_ecriture >= start,
                LigneComptable.date_ecriture <= end,
                or_(
                    LigneComptable.compte.like("34551%"),
                    LigneComptable.compte.like("34552%"),
                    LigneComptable.compte.like("4455%"),
                ),
            ),
        )
    elif module in {"cpc", "bilan"}:
        start, end = _periode(exercice)  # type: ignore[arg-type]
        condition = _exists_line(
            cabinet_id,
            LigneComptable.date_ecriture >= start,
            LigneComptable.date_ecriture <= end,
        )
    elif module in {"cloture", "controls"}:
        start, end = _periode(exercice)  # type: ignore[arg-type]
        condition = or_(
            _exists_entry(
                cabinet_id,
                EcritureComptable.date_piece >= start,
                EcritureComptable.date_piece <= end,
            ),
            _exists_line(
                cabinet_id,
                LigneComptable.date_ecriture >= start,
                LigneComptable.date_ecriture <= end,
            ),
            exists(select(1).select_from(RegularisationCloture).where(
                RegularisationCloture.cabinet_id == cabinet_id,
                RegularisationCloture.entreprise_id == Entreprise.id,
                RegularisationCloture.exercice == exercice,
            )),
        )
    else:  # Protection si la fonction est appelée hors validation FastAPI.
        raise ValueError(f"Module entreprise inconnu: {module}")

    return select(Entreprise).where(
        Entreprise.cabinet_id == cabinet_id,
        Entreprise.is_active.is_(True),
        Entreprise.creee_automatiquement.is_(False),
        condition,
    ).order_by(Entreprise.nom)


def lister_entreprises_disponibles(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    module: ModuleEntreprise,
    exercice: int | None = None,
) -> list[EntrepriseDisponible]:
    companies = list(db.execute(construire_requete(
        cabinet_id=cabinet_id, module=module, exercice=exercice,
    )).scalars().all())
    counts: dict[uuid.UUID, dict[str, int]] = {}
    if module == "registres" and companies:
        rows = db.execute(select(
            EcritureComptable.entreprise_id,
            EcritureComptable.statut_validation,
            func.count(EcritureComptable.id),
        ).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.entreprise_id.in_([company.id for company in companies]),
            EcritureComptable.statut_validation.in_(STATUTS_REGISTRE_SELECTEUR),
        ).group_by(
            EcritureComptable.entreprise_id,
            EcritureComptable.statut_validation,
        )).all()
        for company_id, status, count in rows:
            counts.setdefault(company_id, {})[getattr(status, "value", str(status))] = int(count)

    return [EntrepriseDisponible(
        id=company.id,
        nom=company.nom,
        ice=company.ice,
        is_active=company.is_active,
        creee_automatiquement=company.creee_automatiquement,
        ecritures_brouillon=counts.get(company.id, {}).get("brouillon", 0),
        ecritures_a_verifier=counts.get(company.id, {}).get("a_verifier", 0),
        ecritures_validees=counts.get(company.id, {}).get("valide", 0),
    ) for company in companies]
