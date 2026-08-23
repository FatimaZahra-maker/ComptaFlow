"""Compte bancaire configuré pour une entreprise suivie.

Le compte bancaire relie les identifiants visibles sur les relevés (RIB/IBAN)
au numéro de compte comptable exact déjà présent dans le plan de l'entreprise.
Aucun numéro comptable n'est inventé par ce modèle.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin


class CompteBancaireEntreprise(
    Base,
    UUIDMixin,
    TimestampMixin,
    CabinetScopedMixin,
):
    __tablename__ = "comptes_bancaires_entreprise"
    __table_args__ = (
        Index(
            "ix_compte_bancaire_entreprise_identification",
            "cabinet_id",
            "entreprise_id",
            "is_active",
        ),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    libelle: Mapped[str] = mapped_column(String(120), nullable=False)
    banque_nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rib: Mapped[str | None] = mapped_column(String(64), nullable=True)
    iban: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bic_swift: Mapped[str | None] = mapped_column(String(24), nullable=True)
    devise: Mapped[str] = mapped_column(String(10), nullable=False, default="MAD")

    # Numéro exact du plan comptable de CETTE entreprise.
    numero_compte_comptable: Mapped[str] = mapped_column(String(30), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return (
            f"<CompteBancaireEntreprise {self.libelle} "
            f"{self.numero_compte_comptable}>"
        )
