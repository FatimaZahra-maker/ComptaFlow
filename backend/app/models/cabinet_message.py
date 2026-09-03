"""Messagerie interne multi-tenant entre les utilisateurs et les administrateurs."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class CabinetMessage(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "cabinet_messages"
    __table_args__ = (
        CheckConstraint("message_type IN ('chat', 'access_request')", name="ck_cabinet_messages_type"),
        CheckConstraint("length(trim(contenu)) > 0", name="ck_cabinet_messages_contenu"),
        Index("ix_cabinet_messages_recipient_unread", "cabinet_id", "recipient_id", "read_at"),
    )

    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="chat", server_default="chat")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taches.id", ondelete="SET NULL"), nullable=True, unique=True,
    )
