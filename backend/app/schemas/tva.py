"""Schémas API TVA V2."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TvaConfigurationUpdate(BaseModel):
    periodicite: Literal["mensuelle", "trimestrielle", "autre"] | None = None
    prorata_applicable: bool | None = None
    prorata_deduction: Decimal | None = Field(default=None, ge=0, le=1)
    retenue_applicable: bool | None = None
    jour_limite_declaration: int | None = Field(default=None, ge=1, le=31)
    delai_saisie_topaze_jours: int | None = Field(default=None, ge=0, le=365)
    compte_tva_collectee: str | None = Field(default=None, max_length=30)
    compte_tva_recuperable_charges: str | None = Field(default=None, max_length=30)
    compte_tva_recuperable_immobilisations: str | None = Field(default=None, max_length=30)
    compte_tva_a_payer: str | None = Field(default=None, max_length=30)
    compte_credit_tva: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_prorata(self):
        if self.prorata_applicable is True and self.prorata_deduction is None:
            raise ValueError("Le prorata doit être fourni lorsqu'il est applicable.")
        return self


class TvaConfigurationOut(TvaConfigurationUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cabinet_id: uuid.UUID
    entreprise_id: uuid.UUID


class TvaRegularisationCreate(BaseModel):
    nature: Literal["augmentation", "diminution", "correction", "retenue"]
    montant: Decimal = Field(gt=0)
    sens: Literal["augmentation", "diminution"]
    motif: str = Field(min_length=3, max_length=500)
    date_regularisation: date
    source: str = Field(default="manuel", max_length=50)
    valider: bool = False

    @property
    def montant_signe(self) -> Decimal:
        return self.montant if self.sens == "augmentation" else -self.montant


class TvaRegularisationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nature: str
    montant_signe: Decimal
    motif: str
    date_regularisation: date
    statut: str
    source: str


class TvaPeriodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entreprise_id: uuid.UUID
    annee: int
    mois: int
    statut: str
    tva_collectee: Decimal
    tva_recuperable_charges: Decimal
    tva_recuperable_immobilisations: Decimal
    credit_anterieur: Decimal
    regularisations: Decimal
    retenues_tva: Decimal
    tva_nette: Decimal
    tva_a_payer: Decimal
    credit_a_reporter: Decimal
    credit_source_periode_id: uuid.UUID | None = None
    calcul_provisoire_at: datetime | None = None
    validee_at: datetime | None = None
    a_verifier: bool
    anomalies: list[str]
    statut_comptable: str
    statut_declaration: str
    date_limite_declaration: date | None = None
    declared_at: datetime | None = None
    declared_by: uuid.UUID | None = None
    declaration_date_reelle: date | None = None
    declaration_reference: str | None = None
    declaration_note: str | None = None
    justificatif_disponible: bool = False
    topaze_entered_at: datetime | None = None
    topaze_entered_by: uuid.UUID | None = None
    topaze_batch_reference: str | None = None


class TvaDeclarationCreate(BaseModel):
    date_declaration: date
    reference: str | None = Field(default=None, max_length=150)
    justificatif_document_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class TvaDeadlineUpdate(BaseModel):
    date_limite: date


class TvaTopazeMark(BaseModel):
    saisie: bool = True
    reference_lot: str | None = Field(default=None, max_length=100)


class TvaPeriodesAnneeOut(BaseModel):
    entreprise_id: uuid.UUID
    annee: int
    periodes: list[TvaPeriodeOut]
    configuration: TvaConfigurationOut | None = None
