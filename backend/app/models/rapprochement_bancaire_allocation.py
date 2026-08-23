"""Allocation d'un mouvement bancaire vers une facture.

Une même opération bancaire peut solder plusieurs factures et une facture peut
être réglée par plusieurs opérations. Le montant affecté est toujours exprimé
en MAD dans la V2 ; les écarts de change seront traités par le moteur Devises V2.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class RapprochementBancaireAllocation(
    Base,
    UUIDMixin,
    TimestampMixin,
    CabinetScopedMixin,
):
    __tablename__ = "rapprochements_bancaires_allocations"
    __table_args__ = (
        UniqueConstraint(
            "mouvement_bancaire_id",
            "ecriture_id",
            name="uq_rapprochement_bancaire_mouvement_ecriture",
        ),
        Index(
            "ix_rapprochement_bancaire_ecriture_statut",
            "cabinet_id",
            "entreprise_id",
            "ecriture_id",
            "statut",
        ),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mouvement_bancaire_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mouvements_bancaires.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ecriture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures_comptables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    montant_affecte: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Devises V2 : le montant bancaire réel, la portion en devise et la valeur
    # comptable initiale sont séparés afin de préserver les paiements partiels.
    montant_devise_affecte: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    valeur_comptable_mad: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    montant_reglement_mad: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    ecart_change_mad: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    # sans_ecart | gain | perte | a_verifier
    nature_ecart_change: Mapped[str | None] = mapped_column(String(20), nullable=True)
    compte_ecart_change: Mapped[str | None] = mapped_column(String(30), nullable=True)
    statut_ecart_change: Mapped[str] = mapped_column(
        String(20), nullable=False, default="non_requis"
    )
    raison_ecart_change: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # propose | automatique | confirme
    statut: Mapped[str] = mapped_column(String(30), nullable=False, default="propose")
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    raison: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirme_par: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    date_confirmation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
