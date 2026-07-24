"""
app/models/base.py

Mixins communs. Le "Base" déclaratif lui-même vit dans app/core/database.py
(pas ici) pour que toute l'app partage la même source de connexion DB.
"""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, declared_attr


class UUIDMixin:
    """UUID plutôt qu'un entier auto-incrémenté : impossible de deviner
    ou d'énumérer les IDs d'un cabinet à un autre (sécurité)."""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """Horodatage automatique sur chaque table."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CabinetScopedMixin:
    """
    RÈGLE DE SÉCURITÉ FONDAMENTALE (§6 du cahier des charges) :
    toute table métier a un cabinet_id. Chaque requête doit filtrer dessus
    pour qu'un cabinet ne voie JAMAIS les données d'un autre.
    """
    @declared_attr
    def cabinet_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("cabinets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )