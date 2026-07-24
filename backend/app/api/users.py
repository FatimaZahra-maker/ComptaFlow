"""
backend/app/api/users.py

Routes de gestion des utilisateurs du cabinet.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import get_current_user, require_role
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.models.enums import RoleEnum
from app.schemas.user import UserOut, UserCreate

router = APIRouter(prefix="/users", tags=["users"])

_ROLES_ADMIN = (RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN)


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_ADMIN)),
):
    email_existe = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if email_existe is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur avec cet email existe déjà.",
        )

    nouvel_utilisateur = User(
        cabinet_id=current_user.cabinet_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        nom=payload.nom,
        prenom=payload.prenom,
        role=payload.role,
    )
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)
    return nouvel_utilisateur


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_ADMIN)),
):
    query = (
        select(User)
        .where(User.cabinet_id == current_user.cabinet_id)
        .order_by(User.nom, User.prenom)
    )
    return db.execute(query).scalars().all()


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_ADMIN)),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte.",
        )

    utilisateur = db.execute(
        select(User).where(
            User.id == user_id,
            User.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()
    if utilisateur is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    utilisateur.is_active = False
    db.commit()
    db.refresh(utilisateur)
    return utilisateur