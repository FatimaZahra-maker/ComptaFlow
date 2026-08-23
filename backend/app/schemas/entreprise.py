"""
app/schemas/entreprise.py

Schéma de sortie pour lister les entreprises d'un cabinet — alimente la
colonne "Entreprises" de la page Chronos.
"""
import uuid
from pydantic import BaseModel, ConfigDict


class EntrepriseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    ice: str | None
    creee_automatiquement: bool


class EntrepriseDisponibleOut(EntrepriseOut):
    ecritures_brouillon: int = 0
    ecritures_a_verifier: int = 0
    ecritures_validees: int = 0
