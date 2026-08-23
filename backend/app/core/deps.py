"""
backend/app/core/deps.py

Dependencies FastAPI reutilisables :
- get_current_user : protege une route en exigeant un JWT valide, et
  fournit l'utilisateur courant a la route.
- require_role : en plus de get_current_user, bloque l'acces aux
  utilisateurs dont le role n'est pas dans la liste autorisee (403).
  Utilisee pour les routes de validation comptable (MVC3), reservees
  a Expert-Comptable et Chef de Mission.
"""
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.enums import RoleEnum

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expire",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: RoleEnum):
    """
    Fabrique une dependency qui exige a la fois un JWT valide (via
    get_current_user) ET que le role de l'utilisateur fasse partie de
    `roles`. Usage dans une route :

        current_user: User = Depends(require_role(RoleEnum.EXPERT_COMPTABLE, RoleEnum.CHEF_MISSION))
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : rôle insuffisant pour cette action.",
            )
        return current_user

    return dependency
