"""app/models/compte_comptable_entreprise.py

Plan comptable exact propre à chaque entreprise suivie.

Cette table ne contient jamais de comptes « globaux » au cabinet :
un même numéro peut exister dans plusieurs entreprises, mais chaque ligne
reste strictement scoppée par cabinet_id + entreprise_id.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class CompteComptableEntreprise(
    Base,
    UUIDMixin,
    TimestampMixin,
    CabinetScopedMixin,
):
    __tablename__ = "comptes_comptables_entreprise"
    __table_args__ = (
        UniqueConstraint(
            "cabinet_id",
            "entreprise_id",
            "numero_compte",
            name="uq_compte_comptable_entreprise_numero",
        ),
        Index(
            "ix_compte_comptable_entreprise_famille",
            "cabinet_id",
            "entreprise_id",
            "famille_cgnc",
        ),
        Index(
            "ix_compte_comptable_entreprise_tiers",
            "cabinet_id",
            "entreprise_id",
            "type_usage",
            "tiers_normalise",
        ),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    numero_compte: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    libelle: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Famille CGNC utilisée par le moteur, ex. 6131, 34552, 4411.
    # Elle peut rester vide : le moteur sait aussi vérifier le préfixe
    # du numéro de compte exact.
    famille_cgnc: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Valeurs contrôlées par les schémas/services :
    # ht | tva | fournisseur | client | banque | gain_change |
    # perte_change | autre
    type_usage: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="autre",
    )

    # Pour les comptes HT : location, matieres_premieres, etc.
    nature_comptable: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Pour les comptes tiers individualisés.
    tiers_nom: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    tiers_normalise: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Permet d'identifier explicitement FRS DIVERS / CLIENT DIVERS
    # dans le plan propre à l'entreprise.
    est_divers: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manuel",
    )

    def __repr__(self) -> str:
        return (
            f"<CompteComptableEntreprise "
            f"{self.numero_compte} {self.libelle}>"
        )
