"""Schemas API des controles globaux de pre-cloture V1."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


NiveauControle = Literal["bloquant", "important", "avertissement", "information"]


class AnomalieControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    module: str
    niveau: NiveauControle
    titre: str
    description: str
    entreprise_id: uuid.UUID
    exercice: int
    objet_type: str
    objet_id: uuid.UUID | None = None
    route_frontend: str | None = None
    metadata: dict[str, Any]


class ResumeModuleControleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    module: str
    statut: str
    total_anomalies: int
    bloquants: int
    importants: int
    avertissements: int
    informations: int


class PreClotureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entreprise_id: uuid.UUID
    exercice: int
    score: int
    statut: str
    resume: dict[str, ResumeModuleControleOut]
    anomalies: list[AnomalieControleOut]
    avertissement_score: str
    source_calcul: str
