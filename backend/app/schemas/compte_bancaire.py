"""Schémas des comptes bancaires configurés par entreprise."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompteBancaireBase(BaseModel):
    entreprise_id: uuid.UUID
    libelle: str = Field(min_length=1, max_length=120)
    banque_nom: str | None = Field(default=None, max_length=120)
    rib: str | None = Field(default=None, max_length=64)
    iban: str | None = Field(default=None, max_length=64)
    bic_swift: str | None = Field(default=None, max_length=24)
    devise: str = Field(default="MAD", min_length=3, max_length=10)
    numero_compte_comptable: str = Field(min_length=1, max_length=30)

    @field_validator("devise")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class CompteBancaireCreate(CompteBancaireBase):
    pass


class CompteBancaireUpdate(BaseModel):
    libelle: str | None = Field(default=None, min_length=1, max_length=120)
    banque_nom: str | None = Field(default=None, max_length=120)
    rib: str | None = Field(default=None, max_length=64)
    iban: str | None = Field(default=None, max_length=64)
    bic_swift: str | None = Field(default=None, max_length=24)
    devise: str | None = Field(default=None, min_length=3, max_length=10)
    numero_compte_comptable: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None

    @field_validator("devise")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CompteBancaireOut(CompteBancaireBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
