"""Schémas de sortie du registre comptable et de la TVA mensuelle."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.ecriture import EcritureOut


class RegistreOptionOut(BaseModel):
    """Combinaison de filtres contenant au moins une écriture validée."""

    entreprise_id: uuid.UUID
    categorie: str
    annee: int
    mois: int
    nombre: int


class RegistreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    categorie: str
    entreprise_id: uuid.UUID
    annee: int
    mois: int

    nombre: int
    total_ht: Decimal
    total_tva: Decimal
    total_ttc: Decimal

    lignes: list[EcritureOut]


class TvaMensuelle(BaseModel):
    mois: int
    annee: int
    tva_collectee: str
    tva_deductible: str
    tva_nette: str
    nombre_ecritures: int


class TvaAnnuelleOut(BaseModel):
    entreprise_id: uuid.UUID
    annee: int
    mensualites: list[TvaMensuelle]
    total_tva_collectee: str
    total_tva_deductible: str
    total_tva_nette: str
