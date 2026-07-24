"""
backend/app/schemas/user.py

Schemas Pydantic pour tout ce qui touche a "User" cote API.
"""
import uuid
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.enums import RoleEnum


class UserBase(BaseModel):
    email: EmailStr
    nom: str
    prenom: str


class UserCreate(UserBase):
    """Ce que le CLIENT envoie pour CREER un utilisateur."""
    password: str = Field(min_length=8, description="Mot de passe en clair, sera hashe avant stockage")
    role: RoleEnum


class UserUpdate(BaseModel):
    """Ce que le CLIENT envoie pour MODIFIER un utilisateur existant."""
    role: RoleEnum | None = None
    is_active: bool | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(UserBase):
    """Ce que l'API RENVOIE au client -- jamais hashed_password."""
    id: uuid.UUID
    role: RoleEnum
    is_active: bool

    model_config = ConfigDict(from_attributes=True)