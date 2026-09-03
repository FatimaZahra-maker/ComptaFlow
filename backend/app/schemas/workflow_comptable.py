"""Schémas du suivi documentaire et du verrouillage ComptaFlow."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentAttenduCreate(BaseModel):
    type_document: str = Field(min_length=2, max_length=80)
    frequence: str = Field(min_length=2, max_length=30)
    periode_debut: date
    periode_fin: date
    date_limite_reception: date
    nombre_attendu: int | None = Field(default=None, ge=0)
    responsable_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def dates_coherentes(self):
        if self.periode_fin < self.periode_debut:
            raise ValueError("La fin de période doit suivre son début.")
        return self


class DocumentAttenduOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entreprise_id: uuid.UUID
    type_document: str
    frequence: str
    periode_debut: date
    periode_fin: date
    date_limite_reception: date
    nombre_attendu: int | None
    responsable_id: uuid.UUID | None
    complete_manuellement: bool
    complete_at: datetime | None
    documents_recus: int = 0
    documents_manquants: int | None = None
    jours_retard: int = 0
    statut: str = "en_attente"


class PeriodeTravailCreate(BaseModel):
    exercice: int = Field(ge=2000, le=2100)
    periode_debut: date
    periode_fin: date
    date_limite_saisie_topaze: date | None = None

    @model_validator(mode="after")
    def dates_coherentes(self):
        if self.periode_fin < self.periode_debut:
            raise ValueError("La fin de période doit suivre son début.")
        return self


class PeriodeTravailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entreprise_id: uuid.UUID
    exercice: int
    periode_debut: date
    periode_fin: date
    date_limite_saisie_topaze: date | None
    verrouillee: bool
    locked_at: datetime | None
    locked_by: uuid.UUID | None
    reopened_at: datetime | None
    reopened_by: uuid.UUID | None
    reopen_reason: str | None


class ReouverturePeriode(BaseModel):
    justification: str = Field(min_length=5, max_length=1000)
