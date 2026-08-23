"""Périodes, configuration, crédits et régularisations TVA V2."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class TvaConfigurationEntreprise(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "tva_configurations_entreprise"
    __table_args__ = (
        UniqueConstraint("cabinet_id", "entreprise_id", name="uq_tva_configuration_tenant"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # mensuelle | trimestrielle | autre ; NULL signifie non configuré.
    periodicite: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prorata_applicable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    prorata_deduction: Mapped[Decimal | None] = mapped_column(Numeric(7, 6), nullable=True)
    retenue_applicable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TvaPeriode(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "tva_periodes"
    __table_args__ = (
        UniqueConstraint("cabinet_id", "entreprise_id", "annee", "mois", name="uq_tva_periode_tenant_mois"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annee: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mois: Mapped[int] = mapped_column(Integer, nullable=False)
    # provisoire | validee | cloturee
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="provisoire")

    tva_collectee: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tva_recuperable_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tva_recuperable_immobilisations: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit_anterieur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    regularisations: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    retenues_tva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tva_nette: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tva_a_payer: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    credit_a_reporter: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    credit_source_periode_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tva_periodes.id", ondelete="SET NULL"), nullable=True
    )
    calcul_provisoire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validee_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validee_par: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    a_verifier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    anomalies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_calcul: Mapped[str] = mapped_column(String(50), nullable=False, default="lignes_comptables_validees")


class TvaRegularisation(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "tva_regularisations"

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    periode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tva_periodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # augmentation | diminution | correction | retenue
    nature: Mapped[str] = mapped_column(String(20), nullable=False)
    # Montant signé explicite ; aucune convention fiscale n'est déduite.
    montant_signe: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    motif: Mapped[str] = mapped_column(String(500), nullable=False)
    date_regularisation: Mapped[date] = mapped_column(Date, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="brouillon")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manuel")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TvaCreditUtilisation(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "tva_credit_utilisations"
    __table_args__ = (
        UniqueConstraint("periode_source_id", name="uq_tva_credit_source_utilisee"),
        UniqueConstraint("periode_destination_id", name="uq_tva_credit_destination"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    periode_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tva_periodes.id", ondelete="RESTRICT"), nullable=False
    )
    periode_destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tva_periodes.id", ondelete="RESTRICT"), nullable=False
    )
    montant_utilise: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    utilise_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utilise_par: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
