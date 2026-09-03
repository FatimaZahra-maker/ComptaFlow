"""
backend/app/api/auth.py

Route de connexion. Verifie email + mot de passe, renvoie un token JWT
si c'est correct.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserLogin
from app.schemas.auth import Token
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    # On cherche l'utilisateur par email. scalar_one_or_none() renvoie
    # soit l'utilisateur, soit None -- jamais d'erreur si rien n'est trouve.
    user = db.execute(
        select(User).where(User.email == credentials.email)
    ).scalar_one_or_none()

    # Volontairement le MEME message d'erreur que l'email n'existe pas
    # OU que le mot de passe soit faux -- ne jamais reveler laquelle
    # des deux choses est fausse (ca aiderait un attaquant a deviner
    # quels emails existent dans ta base).
    if user is None or not verify_password(credentials.password, user.hashed_password):
        if user is not None:
            audit_service.enregistrer(
                db, user=user, action=audit_service.AuditAction.LOGIN_FAILED,
                resource_type="session", status="failed",
                description="Tentative de connexion échouée.",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    if not user.is_active:
        audit_service.enregistrer(
            db, user=user, action=audit_service.AuditAction.LOGIN_FAILED,
            resource_type="session", status="failed",
            description="Connexion refusée : compte désactivé.",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte desactive",
        )

    user.last_login = datetime.now(timezone.utc)
    audit_service.enregistrer(
        db, user=user, action=audit_service.AuditAction.LOGIN_SUCCEEDED,
        resource_type="session", description="Connexion réussie.",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)
