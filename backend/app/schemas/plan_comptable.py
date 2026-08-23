"""app/schemas/plan_comptable.py"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TypeUsageCompte = Literal[
    "ht",
    "tva",
    "fournisseur",
    "client",
    "banque",
    "gain_change",
    "perte_change",
    "autre",
]


class CompteComptableBase(BaseModel):
    numero_compte: str = Field(min_length=3, max_length=30)
    libelle: str = Field(min_length=1, max_length=255)
    famille_cgnc: str | None = Field(default=None, max_length=20)
    type_usage: TypeUsageCompte = "autre"
    nature_comptable: str | None = Field(default=None, max_length=100)
    tiers_nom: str | None = Field(default=None, max_length=255)
    est_divers: bool = False
    is_active: bool = True

    @field_validator("numero_compte")
    @classmethod
    def valider_numero_compte(cls, valeur: str) -> str:
        propre = "".join(car for car in valeur.strip() if car.isdigit())
        if len(propre) < 3:
            raise ValueError("Le numéro de compte doit contenir au moins 3 chiffres.")
        return propre

    @field_validator("famille_cgnc")
    @classmethod
    def valider_famille(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        propre = "".join(car for car in valeur.strip() if car.isdigit())
        return propre or None

    @field_validator("libelle", "nature_comptable", "tiers_nom")
    @classmethod
    def nettoyer_texte(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        propre = " ".join(valeur.strip().split())
        return propre or None


class CompteComptableCreate(CompteComptableBase):
    pass


class CompteComptableUpdate(BaseModel):
    libelle: str | None = Field(default=None, min_length=1, max_length=255)
    famille_cgnc: str | None = Field(default=None, max_length=20)
    type_usage: TypeUsageCompte | None = None
    nature_comptable: str | None = Field(default=None, max_length=100)
    tiers_nom: str | None = Field(default=None, max_length=255)
    est_divers: bool | None = None
    is_active: bool | None = None


class CompteComptableOut(CompteComptableBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cabinet_id: uuid.UUID
    entreprise_id: uuid.UUID
    tiers_normalise: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class ImportPlanComptableRequest(BaseModel):
    comptes: list[CompteComptableCreate] = Field(min_length=1, max_length=5000)


class ImportPlanComptableResult(BaseModel):
    crees: int
    mis_a_jour: int
    total: int
