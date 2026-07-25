"""
app/api/cabinet.py

Routes de consultation/modification des informations du cabinet
(page Paramètres). La modification est réservée aux rôles admin --
un collaborateur ne doit pas pouvoir changer l'ICE du cabinet.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User
from app.models.cabinet import Cabinet
from app.models.enums import RoleEnum
from app.schemas.cabinet import CabinetOut, CabinetUpdate

router = APIRouter(prefix="/cabinet", tags=["cabinet"])

_ROLES_ADMIN = (RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN)


# Renvoie les informations du cabinet de l'utilisateur connecté --
# accessible à tous les rôles (lecture seule pour un collaborateur).
@router.get("", response_model=CabinetOut)
def get_cabinet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cabinet = db.query(Cabinet).filter(Cabinet.id == current_user.cabinet_id).first()
    if cabinet is None:
        raise HTTPException(status_code=404, detail="Cabinet introuvable.")
    return cabinet


# Modifie les informations du cabinet (formulaire Paramètres) --
# réservé aux rôles admin. Ne touche que les champs fournis dans le
# payload, grâce à exclude_unset=True.
@router.patch("", response_model=CabinetOut)
def update_cabinet(
    payload: CabinetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_ADMIN)),
):
    cabinet = db.query(Cabinet).filter(Cabinet.id == current_user.cabinet_id).first()
    if cabinet is None:
        raise HTTPException(status_code=404, detail="Cabinet introuvable.")

    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(cabinet, champ, valeur)

    db.commit()
    db.refresh(cabinet)
    return cabinet