"""API des regularisations de cloture V1."""
from __future__ import annotations

import uuid
from collections import Counter
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.entreprise import Entreprise
from app.models.enums import RoleEnum
from app.models.regularisation_cloture import RegularisationCloture
from app.models.user import User
from app.schemas.cloture import (
    AnnulationCloture, RegularisationClotureCreate, RegularisationClotureOut,
    RegularisationClotureUpdate, SyntheseClotureOut,
)
from app.services import cloture_service

router = APIRouter(prefix="/accounting/cloture", tags=["accounting", "cloture"])
_ROLES_VALIDATION = (RoleEnum.ADMIN_CABINET, RoleEnum.EXPERT_COMPTABLE, RoleEnum.CHEF_MISSION)


def _ensure_company(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> None:
    if db.execute(select(Entreprise.id).where(
        Entreprise.id == entreprise_id, Entreprise.cabinet_id == cabinet_id
    )).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")


def _get(db: Session, item_id: uuid.UUID, user: User, entreprise_id: uuid.UUID) -> RegularisationCloture:
    item = db.execute(select(RegularisationCloture).where(
        RegularisationCloture.id == item_id,
        RegularisationCloture.cabinet_id == user.cabinet_id,
        RegularisationCloture.entreprise_id == entreprise_id,
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Regularisation de cloture introuvable.")
    return item


@router.get("", response_model=list[RegularisationClotureOut])
def list_items(
    entreprise_id: uuid.UUID, exercice: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    return db.execute(select(RegularisationCloture).where(
        RegularisationCloture.cabinet_id == current_user.cabinet_id,
        RegularisationCloture.entreprise_id == entreprise_id,
        RegularisationCloture.exercice == exercice,
    ).order_by(RegularisationCloture.date_ecriture, RegularisationCloture.created_at)).scalars().all()


@router.post("", response_model=RegularisationClotureOut)
def create_item(
    entreprise_id: uuid.UUID, payload: RegularisationClotureCreate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    item = RegularisationCloture(
        cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id,
        created_by=current_user.id, **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=RegularisationClotureOut)
def update_item(
    item_id: uuid.UUID, entreprise_id: uuid.UUID, payload: RegularisationClotureUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    item = _get(db, item_id, current_user, entreprise_id)
    if item.statut not in {"brouillon", "a_verifier"}:
        raise HTTPException(status_code=422, detail="Seul un brouillon ou un element a verifier peut etre modifie.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    if item.date_ecriture.year != item.exercice:
        raise HTTPException(status_code=422, detail="La date d'ecriture doit appartenir a l'exercice.")
    item.statut = "brouillon"
    item.anomalies = []
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/valider", response_model=RegularisationClotureOut)
def validate_item(
    item_id: uuid.UUID, entreprise_id: uuid.UUID, db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    item = _get(db, item_id, current_user, entreprise_id)
    if item.statut == "comptabilisee":
        return item
    cloture_service.valider_regularisation(db, item, current_user.id)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/generer", response_model=RegularisationClotureOut)
def generate_item(
    item_id: uuid.UUID, entreprise_id: uuid.UUID, db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    item = _get(db, item_id, current_user, entreprise_id)
    try:
        cloture_service.generer_lignes(db, item)
        db.commit()
        db.refresh(item)
        return item
    except ValueError as exc:
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{item_id}/annuler", response_model=RegularisationClotureOut)
def cancel_item(
    item_id: uuid.UUID, entreprise_id: uuid.UUID, payload: AnnulationCloture,
    db: Session = Depends(get_db), current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    item = _get(db, item_id, current_user, entreprise_id)
    cloture_service.annuler_regularisation(db, item, payload.motif)
    db.commit()
    db.refresh(item)
    return item


@router.get("/synthese/annuelle", response_model=SyntheseClotureOut)
def summary(
    entreprise_id: uuid.UUID, exercice: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    items = db.execute(select(RegularisationCloture).where(
        RegularisationCloture.cabinet_id == current_user.cabinet_id,
        RegularisationCloture.entreprise_id == entreprise_id,
        RegularisationCloture.exercice == exercice,
    )).scalars().all()
    statuses = Counter(item.statut for item in items)
    return SyntheseClotureOut(
        entreprise_id=entreprise_id, exercice=exercice, total_regularisations=len(items),
        montant_total=sum((Decimal(item.montant) for item in items if item.statut != "annulee"), Decimal("0")),
        par_statut=dict(statuses), a_verifier=statuses.get("a_verifier", 0),
    )
