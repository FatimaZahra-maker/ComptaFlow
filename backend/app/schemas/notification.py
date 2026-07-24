"""
app/schemas/notification.py

Schéma de sortie des notifications, enrichi avec le contexte entreprise
(pour répondre à "rappel pour quelle entreprise exactement") et des
schémas d'agrégats pour alimenter les graphiques de la page dédiée.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str              # identifiant synthétique, ex: "document_erreur-<uuid>"
    type: str
    message: str
    route: str            # route frontend vers laquelle naviguer au clic
    created_at: datetime
    entreprise_id: uuid.UUID | None = None
    entreprise_nom: str | None = None


class NotificationsOut(BaseModel):
    total: int
    notifications: list[NotificationOut]


class RepartitionParType(BaseModel):
    type: str
    total: int


class RepartitionParEntreprise(BaseModel):
    entreprise_id: uuid.UUID | None
    entreprise_nom: str
    total: int


class NotificationsStatsOut(BaseModel):
    par_type: list[RepartitionParType]
    par_entreprise: list[RepartitionParEntreprise]