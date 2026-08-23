"""app/models/taux_change_bam.py

Cache local des cours de change Bank Al-Maghrib utilisés par ComptaFlow.

Le cache est global : un cours BAM pour une date/devise donnée est identique
pour tous les cabinets. Les documents comptables restent, eux, scoppés par
cabinet et entreprise.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TauxChangeBAM(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "taux_change_bam"
    __table_args__ = (
        UniqueConstraint(
            "date_cours",
            "devise",
            "source",
            name="uq_taux_change_bam_date_devise_source",
        ),
    )

    date_cours: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    devise: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Exemple : 1 EUR, mais 100 JPY sur la table BAM des billets étrangers.
    unite_cotation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    libelle_bam: Mapped[str] = mapped_column(String(120), nullable=False)

    # On conserve plus de décimales que BAM n'en publie actuellement afin de
    # ne jamais tronquer un futur taux plus précis.
    cours_achat: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    cours_vente: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)

    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="bam_billets_etrangers"
    )
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<TauxChangeBAM {self.date_cours} {self.devise} "
            f"achat={self.cours_achat} vente={self.cours_vente}>"
        )
