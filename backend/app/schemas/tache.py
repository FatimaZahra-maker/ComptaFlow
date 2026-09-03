"""
app/schemas/tache.py

Schémas Pydantic pour Rappels & Tâches. TacheOut inclut est_en_retard,
calculé côté backend (date_echeance < aujourd'hui et statut != terminee)
plutôt que côté frontend, pour que la définition du retard soit unique
et cohérente partout (page dédiée, notifications, tableau de bord).
"""
import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatutTacheEnum, PrioriteTacheEnum, RecurrenceTacheEnum


class TacheCreate(BaseModel):
    entreprise_id: uuid.UUID | None = None
    assignee_a: uuid.UUID | None = None
    titre: str = Field(min_length=1, max_length=255)
    description: str | None = None
    date_echeance: date
    heure_echeance: time | None = None
    priorite: PrioriteTacheEnum = PrioriteTacheEnum.NORMALE
    recurrence: RecurrenceTacheEnum = RecurrenceTacheEnum.AUCUNE


class TacheUpdate(BaseModel):
    titre: str | None = None
    description: str | None = None
    date_echeance: date | None = None
    heure_echeance: time | None = None
    statut: StatutTacheEnum | None = None
    priorite: PrioriteTacheEnum | None = None
    recurrence: RecurrenceTacheEnum | None = None
    assignee_a: uuid.UUID | None = None


class TacheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID | None
    entreprise_nom: str | None = None
    cree_par: uuid.UUID
    assignee_a: uuid.UUID | None
    assignee_nom: str | None = None

    titre: str
    description: str | None
    date_echeance: date
    heure_echeance: time | None
    statut: str
    priorite: str
    recurrence: str
    created_at: datetime

    est_en_retard: bool = False
