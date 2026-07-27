"""
app/api/rappels.py

Route unique qui expose les 2 listes d'alertes automatiques de la page
Rappels & Tâches (voir app/services/alertes_service.py pour le calcul).
Séparée volontairement de app/api/taches.py : les tâches manuelles
(CRUD, stockées en base) et les alertes automatiques (calculées à la
volée) sont deux logiques différentes, pour ne pas mélanger les deux
concepts dans un seul fichier.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.rappel import AlertesRappelsOut
from app.services.alertes_service import (
    lister_ecritures_non_saisies,
    lister_entreprises_en_retard,
)

router = APIRouter(prefix="/rappels", tags=["rappels"])


@router.get("/alertes", response_model=AlertesRappelsOut)
def get_alertes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Renvoie en un seul appel les écritures non saisies + les entreprises en retard."""
    return AlertesRappelsOut(
        non_saisies=lister_ecritures_non_saisies(db, current_user.cabinet_id),
        entreprises_en_retard=lister_entreprises_en_retard(db, current_user.cabinet_id),
    )