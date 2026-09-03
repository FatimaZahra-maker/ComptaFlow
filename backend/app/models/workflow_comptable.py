"""Configuration et traçabilité du workflow pré-comptable ComptaFlow."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class AnomalieComptable(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "anomalies_comptables"

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures_comptables.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tva_periode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tva_periodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type_anomalie: Mapped[str] = mapped_column(String(80), nullable=False)
    gravite: Mapped[str] = mapped_column(String(20), nullable=False, default="bloquante")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    champ_concerne: Mapped[str | None] = mapped_column(String(100), nullable=True)
    valeur_detectee: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class DocumentAttenduConfiguration(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "documents_attendus_configuration"
    __table_args__ = (
        UniqueConstraint(
            "cabinet_id", "entreprise_id", "type_document", "periode_debut", "periode_fin",
            name="uq_document_attendu_tenant_periode",
        ),
        CheckConstraint("nombre_attendu IS NULL OR nombre_attendu >= 0", name="ck_document_attendu_nombre"),
        CheckConstraint("periode_fin >= periode_debut", name="ck_document_attendu_periode"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_document: Mapped[str] = mapped_column(String(80), nullable=False)
    frequence: Mapped[str] = mapped_column(String(30), nullable=False)
    periode_debut: Mapped[date] = mapped_column(Date, nullable=False)
    periode_fin: Mapped[date] = mapped_column(Date, nullable=False)
    date_limite_reception: Mapped[date] = mapped_column(Date, nullable=False)
    nombre_attendu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    complete_manuellement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    complete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    complete_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class PeriodeTravail(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "periodes_travail"
    __table_args__ = (
        UniqueConstraint(
            "cabinet_id", "entreprise_id", "periode_debut", "periode_fin",
            name="uq_periode_travail_tenant",
        ),
        CheckConstraint("periode_fin >= periode_debut", name="ck_periode_travail_dates"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercice: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    periode_debut: Mapped[date] = mapped_column(Date, nullable=False)
    periode_fin: Mapped[date] = mapped_column(Date, nullable=False)
    date_limite_saisie_topaze: Mapped[date | None] = mapped_column(Date, nullable=True)
    verrouillee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
