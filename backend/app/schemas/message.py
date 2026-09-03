import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import PrioriteTacheEnum, RecurrenceTacheEnum


class AccessRenewalRequest(BaseModel):
    email: EmailStr
    message: str | None = Field(default=None, max_length=500)


class AccessRenewalResponse(BaseModel):
    message: str


class MessageCreate(BaseModel):
    recipient_id: uuid.UUID
    contenu: str = Field(min_length=1, max_length=2000)


class MessageContactOut(BaseModel):
    id: uuid.UUID
    nom_complet: str
    email: str
    role: str
    is_active: bool
    unread_count: int = 0


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID | None
    recipient_id: uuid.UUID | None
    sender_name: str | None
    recipient_name: str | None
    contenu: str
    message_type: str
    read_at: datetime | None
    task_id: uuid.UUID | None
    created_at: datetime
    is_mine: bool


class MessageTaskCreate(BaseModel):
    titre: str | None = Field(default=None, max_length=255)
    date_echeance: date
    heure_echeance: time | None = None
    priorite: PrioriteTacheEnum = PrioriteTacheEnum.NORMALE
    recurrence: RecurrenceTacheEnum = RecurrenceTacheEnum.AUCUNE
