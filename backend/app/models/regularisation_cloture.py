"""Regularisations de cloture et piste d'audit associee."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class RegularisationCloture(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "regularisations_cloture"
    __table_args__ = (
        UniqueConstraint("report_source_id", name="uq_regularisation_cloture_report_source"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercice: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date_ecriture: Mapped[date] = mapped_column(Date, nullable=False)
    type_regularisation: Mapped[str] = mapped_column(String(40), nullable=False)
    libelle: Mapped[str] = mapped_column(String(500), nullable=False)
    montant: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    compte_debit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    compte_credit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="brouillon")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manuel")
    anomalies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    donnees_calcul: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    a_extourner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    date_extourne: Mapped[date | None] = mapped_column(Date, nullable=True)
    report_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regularisations_cloture.id", ondelete="RESTRICT"), nullable=True
    )
    motif_annulation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
