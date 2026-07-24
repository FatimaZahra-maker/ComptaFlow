"""
app/api/entreprises.py

Route de consultation des entreprises du cabinet — alimente la colonne
"Entreprises" de la page Chronos.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.entreprise import Entreprise
from app.schemas.entreprise import EntrepriseOut

router = APIRouter(prefix="/entreprises", tags=["entreprises"])


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