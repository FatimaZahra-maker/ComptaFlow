"""
app/schemas/cabinet.py

Schémas Pydantic pour la page Paramètres : consultation et
modification des informations du cabinet (nom, ICE, coordonnées).
"""
from pydantic import BaseModel, ConfigDict
import uuid


# Ce que l'API renvoie pour afficher les informations du cabinet dans
# la page Paramètres.
class CabinetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    ice: str | None
    adresse: str | None
    telephone: str | None
    email: str | None
    is_active: bool


# Ce que le client envoie pour MODIFIER les informations du cabinet.
# Tous les champs sont optionnels : seuls ceux fournis sont modifiés
# (exclude_unset côté route), pour ne jamais écraser un champ non
# touché par le formulaire.
class CabinetUpdate(BaseModel):
    nom: str | None = None
    ice: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    email: str | None = None