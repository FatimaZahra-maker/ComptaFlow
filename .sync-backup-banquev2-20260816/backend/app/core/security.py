"""
backend/app/core/security.py

Fonctions de sécurité centralisées :

- hash des mots de passe ;
- vérification des mots de passe ;
- création des JWT ;
- lecture et validation des JWT.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from typing import Any

from jose import (
    JWTError,
    jwt,
)

from passlib.context import CryptContext

from app.core.config import settings


# ---------------------------------------------------------
# MOTS DE PASSE
# ---------------------------------------------------------

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(
    plain_password: str,
) -> str:
    """
    Transforme un mot de passe en hash bcrypt.

    Le mot de passe original n'est jamais stocké dans
    la base de données.
    """

    return pwd_context.hash(
        plain_password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Vérifie qu'un mot de passe correspond
    au hash stocké dans la base.
    """

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# ---------------------------------------------------------
# JWT
# ---------------------------------------------------------

ALGORITHM = "HS256"


def create_access_token(
    data: dict[str, Any],
) -> str:
    """
    Crée un JWT signé avec SECRET_KEY.

    La durée du token n'est plus hardcodée ici.
    Elle vient maintenant du fichier .env via :

    ACCESS_TOKEN_EXPIRE_MINUTES
    """

    to_encode = data.copy()

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=(
                settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        )
    )

    to_encode.update(
        {
            "exp": expire,
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Vérifie :

    - la signature du JWT ;
    - sa date d'expiration.

    Retourne le contenu si le token est valide.

    Retourne None sinon.
    """

    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

    except JWTError:
        return None