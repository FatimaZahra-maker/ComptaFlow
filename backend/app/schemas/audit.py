"""Schémas explicites de consultation du journal d'audit."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditResourceLink(BaseModel):
    label: str
    resource_type: str
    resource_id: uuid.UUID
    route: str


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cabinet_id: uuid.UUID
    entreprise_id: uuid.UUID | None = None
    entreprise_nom: str | None = None
    user_id: uuid.UUID | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    actor_type: str
    action: str
    module: str
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    description: str | None = None
    status: str
    event_at: datetime
    correlation_id: str | None = None
    item_count: int | None = None
    resource_ids: list[str] = Field(default_factory=list)
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    links: list[AuditResourceLink] = Field(default_factory=list)


class AuditPageOut(BaseModel):
    items: list[AuditEventOut]
    page: int
    page_size: int
    total: int
    pages: int


class AuditFilterOptionsOut(BaseModel):
    actions: list[str]
    modules: list[str]
    roles: list[str]
    statuses: list[str]

