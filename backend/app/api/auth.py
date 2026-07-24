"""
backend/app/api/auth.py

Route de connexion. Verifie email + mot de passe, renvoie un token JWT
si c'est correct.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserLogin
from app.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte desactive",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)