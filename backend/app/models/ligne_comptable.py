"""app/models/ligne_comptable.py

Lignes comptables normalisées Débit / Crédit.

Une ligne provient soit :
- d'une facture (ecriture_id),
- d'un mouvement bancaire rapproché (mouvement_bancaire_id).

Le Grand Livre et la Balance utilisent uniquement les lignes dont
``est_validee`` est vraie. Les montants de cette table sont toujours en MAD ;
les montants originaux en devise restent conservés sur les documents et les
mouvements bancaires.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class LigneComptable(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "lignes_comptables"
    __table_args__ = (
        CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name="ck_ligne_comptable_montants_positifs",
        ),
        CheckConstraint(
            "((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))",
            name="ck_ligne_comptable_un_seul_sens",
        ),
        CheckConstraint(
            "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NULL) "
            "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL AND regularisation_cloture_id IS NULL) "
            "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NOT NULL))",
            name="ck_ligne_comptable_source_unique",
        ),
        UniqueConstraint(
            "ecriture_id",
            "ordre",
            name="uq_ligne_comptable_ecriture_ordre",
        ),
        UniqueConstraint(
            "mouvement_bancaire_id",
            "ordre",
            name="uq_ligne_comptable_mouvement_ordre",
        ),
        UniqueConstraint(
            "regularisation_cloture_id",
            "ordre",
            name="uq_ligne_comptable_cloture_ordre",
        ),
        Index(
            "ix_ligne_comptable_grand_livre",
            "cabinet_id",
            "entreprise_id",
            "date_ecriture",
            "compte",
        ),
        Index(
            "ix_ligne_comptable_validation",
            "cabinet_id",
            "entreprise_id",
            "est_validee",
        ),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ecriture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures_comptables.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    mouvement_bancaire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mouvements_bancaires.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    regularisation_cloture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regularisations_cloture.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    date_ecriture: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    journal: Mapped[str] = mapped_column(String(10), nullable=False)
    numero_piece: Mapped[str | None] = mapped_column(String(100), nullable=True)
    compte: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    libelle: Mapped[str] = mapped_column(String(500), nullable=False)

    debit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )

    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    origine: Mapped[str] = mapped_column(String(20), nullable=False)
    est_validee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<LigneComptable {self.date_ecriture} {self.compte} "
            f"D={self.debit} C={self.credit}>"
        )
