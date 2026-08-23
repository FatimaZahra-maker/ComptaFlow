"""app/api/plan_comptable.py

CRUD du plan comptable exact par entreprise.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.entreprise import Entreprise
from app.models.user import User
from app.schemas.plan_comptable import (
    CompteComptableCreate,
    CompteComptableOut,
    CompteComptableUpdate,
    ImportPlanComptableRequest,
    ImportPlanComptableResult,
)
from app.services.plan_comptable_service import creer_ou_mettre_a_jour_compte


router = APIRouter(
    prefix="/entreprises/{entreprise_id}/plan-comptable",
    tags=["plan-comptable"],
)


def _obtenir_entreprise(
    db: Session,
    entreprise_id: uuid.UUID,
    current_user: User,
) -> Entreprise:
    entreprise = (
        db.query(Entreprise)
        .filter(
            Entreprise.id == entreprise_id,
            Entreprise.cabinet_id == current_user.cabinet_id,
        )
        .first()
    )

    if entreprise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable dans ce cabinet.",
        )

    return entreprise


@router.get("", response_model=list[CompteComptableOut])
def lister_plan_comptable(
    entreprise_id: uuid.UUID,
    recherche: str | None = Query(default=None, max_length=100),
    type_usage: str | None = Query(default=None, max_length=30),
    actifs_seulement: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _obtenir_entreprise(db, entreprise_id, current_user)

    query = db.query(CompteComptableEntreprise).filter(
        CompteComptableEntreprise.cabinet_id == current_user.cabinet_id,
        CompteComptableEntreprise.entreprise_id == entreprise_id,
    )

    if actifs_seulement:
        query = query.filter(CompteComptableEntreprise.is_active.is_(True))

    if type_usage:
        query = query.filter(
            CompteComptableEntreprise.type_usage == type_usage.strip().lower()
        )

    if recherche and recherche.strip():
        terme = f"%{recherche.strip()}%"
        query = query.filter(
            or_(
                CompteComptableEntreprise.numero_compte.ilike(terme),
                CompteComptableEntreprise.libelle.ilike(terme),
                CompteComptableEntreprise.tiers_nom.ilike(terme),
            )
        )

    return query.order_by(CompteComptableEntreprise.numero_compte.asc()).all()


@router.post(
    "",
    response_model=CompteComptableOut,
    status_code=status.HTTP_201_CREATED,
)
def ajouter_compte(
    entreprise_id: uuid.UUID,
    payload: CompteComptableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _obtenir_entreprise(db, entreprise_id, current_user)

    try:
        compte, cree = creer_ou_mettre_a_jour_compte(
            db,
            cabinet_id=current_user.cabinet_id,
            entreprise_id=entreprise_id,
            **payload.model_dump(),
            source="manuel",
        )
        db.commit()
        db.refresh(compte)
        return compte

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch("/{compte_id}", response_model=CompteComptableOut)
def modifier_compte(
    entreprise_id: uuid.UUID,
    compte_id: uuid.UUID,
    payload: CompteComptableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _obtenir_entreprise(db, entreprise_id, current_user)

    compte = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.id == compte_id,
            CompteComptableEntreprise.cabinet_id == current_user.cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
        )
        .first()
    )

    if compte is None:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    data = payload.model_dump(exclude_unset=True)

    try:
        compte, _ = creer_ou_mettre_a_jour_compte(
            db,
            cabinet_id=current_user.cabinet_id,
            entreprise_id=entreprise_id,
            numero_compte=compte.numero_compte,
            libelle=data.get("libelle", compte.libelle),
            famille_cgnc=data.get("famille_cgnc", compte.famille_cgnc),
            type_usage=data.get("type_usage", compte.type_usage),
            nature_comptable=data.get("nature_comptable", compte.nature_comptable),
            tiers_nom=data.get("tiers_nom", compte.tiers_nom),
            est_divers=data.get("est_divers", compte.est_divers),
            is_active=data.get("is_active", compte.is_active),
            source="manuel",
        )
        db.commit()
        db.refresh(compte)
        return compte

    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import", response_model=ImportPlanComptableResult)
def importer_plan_comptable(
    entreprise_id: uuid.UUID,
    payload: ImportPlanComptableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _obtenir_entreprise(db, entreprise_id, current_user)

    crees = 0
    mis_a_jour = 0

    try:
        for item in payload.comptes:
            _, cree = creer_ou_mettre_a_jour_compte(
                db,
                cabinet_id=current_user.cabinet_id,
                entreprise_id=entreprise_id,
                **item.model_dump(),
                source="import_api",
            )
            if cree:
                crees += 1
            else:
                mis_a_jour += 1

        db.commit()

    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ImportPlanComptableResult(
        crees=crees,
        mis_a_jour=mis_a_jour,
        total=len(payload.comptes),
    )


@router.delete("/{compte_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactiver_compte(
    entreprise_id: uuid.UUID,
    compte_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _obtenir_entreprise(db, entreprise_id, current_user)

    compte = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.id == compte_id,
            CompteComptableEntreprise.cabinet_id == current_user.cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
        )
        .first()
    )

    if compte is None:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    compte.is_active = False
    db.commit()
    return None
