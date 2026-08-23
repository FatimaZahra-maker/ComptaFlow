"""Schemas API des regularisations de cloture V1."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TypeRegularisation = Literal[
    "amortissement",
    "provision",
    "stock",
    "charge_constatee_avance",
    "produit_constate_avance",
    "charge_a_payer",
    "produit_a_recevoir",
    "ajustement_manuel",
    "resultat_cloture",
    "report_a_nouveau",
]


class RegularisationClotureCreate(BaseModel):
    exercice: int = Field(ge=2000, le=2100)
    date_ecriture: date
    type_regularisation: TypeRegularisation
    libelle: str = Field(min_length=3, max_length=500)
    montant: Decimal = Field(gt=0)
    compte_debit: str | None = Field(default=None, max_length=30)
    compte_credit: str | None = Field(default=None, max_length=30)
    source: str = Field(default="manuel", max_length=50)
    donnees_calcul: dict[str, Any] = Field(default_factory=dict)
    a_extourner: bool = False
    date_extourne: date | None = None
    report_source_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_ecriture.year != self.exercice:
            raise ValueError("La date d'ecriture doit appartenir a l'exercice.")
        if self.a_extourner and self.date_extourne is None:
            raise ValueError("La date d'extourne doit etre explicitement fournie.")
        return self


class RegularisationClotureUpdate(BaseModel):
    date_ecriture: date | None = None
    libelle: str | None = Field(default=None, min_length=3, max_length=500)
    montant: Decimal | None = Field(default=None, gt=0)
    compte_debit: str | None = Field(default=None, max_length=30)
    compte_credit: str | None = Field(default=None, max_length=30)
    donnees_calcul: dict[str, Any] | None = None
    a_extourner: bool | None = None
    date_extourne: date | None = None


class RegularisationClotureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cabinet_id: uuid.UUID
    entreprise_id: uuid.UUID
    exercice: int
    date_ecriture: date
    type_regularisation: str
    libelle: str
    montant: Decimal
    compte_debit: str | None
    compte_credit: str | None
    statut: str
    source: str
    anomalies: list[str]
    donnees_calcul: dict[str, Any]
    a_extourner: bool
    date_extourne: date | None
    report_source_id: uuid.UUID | None
    motif_annulation: str | None
    validated_at: datetime | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AnnulationCloture(BaseModel):
    motif: str = Field(min_length=3, max_length=1000)


class SyntheseClotureOut(BaseModel):
    entreprise_id: uuid.UUID
    exercice: int
    total_regularisations: int
    montant_total: Decimal
    par_statut: dict[str, int]
    a_verifier: int

