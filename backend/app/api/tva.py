"""API TVA V2, complémentaire à la synthèse comptable V1."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.entreprise import Entreprise
from app.models.enums import RoleEnum
from app.models.tva_periode import TvaConfigurationEntreprise, TvaPeriode, TvaRegularisation
from app.models.user import User
from app.schemas.tva import (
    TvaConfigurationOut,
    TvaConfigurationUpdate,
    TvaPeriodeOut,
    TvaPeriodesAnneeOut,
    TvaRegularisationCreate,
    TvaRegularisationOut,
)
from app.services import tva_comptable_service

router = APIRouter(prefix="/accounting/tva-v2", tags=["accounting", "tva-v2"])
_ROLES_VALIDATION = (
    RoleEnum.ADMIN_CABINET,
    RoleEnum.EXPERT_COMPTABLE,
    RoleEnum.CHEF_MISSION,
)


def _ensure_company(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> None:
    exists = db.execute(
        select(Entreprise.id).where(
            Entreprise.id == entreprise_id,
            Entreprise.cabinet_id == cabinet_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")


def _get_period(
    db: Session,
    period_id: uuid.UUID,
    user: User,
    entreprise_id: uuid.UUID,
) -> TvaPeriode:
    period = db.execute(
        select(TvaPeriode).where(
            TvaPeriode.id == period_id,
            TvaPeriode.cabinet_id == user.cabinet_id,
            TvaPeriode.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="Période TVA introuvable.")
    return period


@router.post("/recalculer", response_model=TvaPeriodesAnneeOut)
def recalculate_periods(
    entreprise_id: uuid.UUID,
    annee: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    periods = tva_comptable_service.recalculer_periodes_tva(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )
    configuration = db.execute(
        select(TvaConfigurationEntreprise).where(
            TvaConfigurationEntreprise.cabinet_id == current_user.cabinet_id,
            TvaConfigurationEntreprise.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    db.commit()
    return TvaPeriodesAnneeOut(
        entreprise_id=entreprise_id,
        annee=annee,
        periodes=[TvaPeriodeOut.model_validate(item) for item in periods],
        configuration=(TvaConfigurationOut.model_validate(configuration) if configuration else None),
    )


@router.put("/configuration/{entreprise_id}", response_model=TvaConfigurationOut)
def update_configuration(
    entreprise_id: uuid.UUID,
    payload: TvaConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    config = db.execute(
        select(TvaConfigurationEntreprise).where(
            TvaConfigurationEntreprise.cabinet_id == current_user.cabinet_id,
            TvaConfigurationEntreprise.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    if config is None:
        config = TvaConfigurationEntreprise(
            cabinet_id=current_user.cabinet_id,
            entreprise_id=entreprise_id,
        )
        db.add(config)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, name, value)
    db.commit()
    db.refresh(config)
    return config


@router.post("/periodes/{period_id}/regularisations", response_model=TvaRegularisationOut)
def create_adjustment(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    payload: TvaRegularisationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    if period.statut == "cloturee":
        raise HTTPException(status_code=422, detail="Période TVA clôturée.")
    adjustment = TvaRegularisation(
        cabinet_id=current_user.cabinet_id,
        entreprise_id=period.entreprise_id,
        periode_id=period.id,
        nature=payload.nature,
        montant_signe=payload.montant_signe,
        motif=payload.motif,
        date_regularisation=payload.date_regularisation,
        statut="validee" if payload.valider else "brouillon",
        source=payload.source,
        created_by=current_user.id,
    )
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


@router.post("/periodes/{period_id}/valider", response_model=TvaPeriodeOut)
def validate_period(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    try:
        tva_comptable_service.valider_periode_tva(
            db,
            periode=period,
            cabinet_id=current_user.cabinet_id,
            entreprise_id=period.entreprise_id,
            user_id=current_user.id,
        )
        db.commit()
        db.refresh(period)
        return period
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
