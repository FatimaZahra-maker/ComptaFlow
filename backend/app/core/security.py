"""
backend/app/core/security.py

Tout ce qui touche a la securite des mots de passe et des connexions :
- hash_password / verify_password : transformer et verifier un mot de passe
- create_access_token / decode_access_token : creer et lire un JWT

Centralise ici pour que cette logique sensible existe a un seul endroit,
jamais dupliquee dans les routes.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

# --- Hash de mot de passe ---
# bcrypt : algorithme de hash volontairement LENT (quelques millisecondes),
# pour rendre une attaque par force brute couteuse. C'est un standard
# reconnu, ne jamais utiliser md5/sha256 seuls pour des mots de passe.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Transforme un mot de passe en clair en hash irreversible.
    'Irreversible' = impossible de retrouver le mot de passe original
    a partir du hash, meme en connaissant l'algorithme.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifie qu'un mot de passe en clair correspond a un hash stocke.
    On ne "dehashe" jamais -- on hash le mot de passe fourni et on
    compare les deux hash entre eux.
    """
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT (JSON Web Token) ---
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # le token expire au bout de 8 heures


def create_access_token(data: dict[str, Any]) -> str:
    """
    Cree un token JWT signe avec notre SECRET_KEY.
    'data' contient generalement {"sub": "id-de-l-utilisateur"}.
    Ce token est envoye au client apres un login reussi. Le client le
    renvoie ensuite a CHAQUE requete (dans le header HTTP
    "Authorization: Bearer <token>") pour prouver son identite sans
    avoir a renvoyer son mot de passe a chaque fois.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Verifie la signature du token (personne ne peut le fabriquer sans
    connaitre SECRET_KEY) et qu'il n'est pas expire.
    Retourne le contenu du token si valide, None sinon.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None