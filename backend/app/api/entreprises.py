"""
app/api/entreprises.py

Route de consultation des entreprises du cabinet — alimente la colonne
"Entreprises" de la page Chronos.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.entreprise import Entreprise
from app.schemas.entreprise import EntrepriseDisponibleOut, EntrepriseOut
from app.services.available_company_service import (
    MODULES_AVEC_EXERCICE,
    ModuleEntreprise,
    lister_entreprises_disponibles,
)

router = APIRouter(prefix="/entreprises", tags=["entreprises"])


@router.get("/available", response_model=list[EntrepriseDisponibleOut])
def list_available_entreprises(
    module: ModuleEntreprise = Query(...),
    exercice: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if module in MODULES_AVEC_EXERCICE and exercice is None:
        raise HTTPException(status_code=422, detail="L'exercice est obligatoire pour ce module.")
    return lister_entreprises_disponibles(
        db,
        cabinet_id=current_user.cabinet_id,
        module=module,
        exercice=exercice,
    )


@router.get("", response_model=list[EntrepriseOut])
def list_entreprises(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Entreprise)
        .where(Entreprise.cabinet_id == current_user.cabinet_id)
        .order_by(Entreprise.nom)
    )
    return db.execute(query).scalars().all()
