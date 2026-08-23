"""app/models/ecriture.py

Résumé d'une écriture issue d'un document Achat/Vente.

Les comptes exacts (tiers, TVA, HT) sont résolus par les règles métier et le
plan comptable propre à l'entreprise. Les lignes Débit/Crédit normalisées sont
stockées séparément dans ``lignes_comptables``.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin
from app.models.enums import StatutValidationEnum, TauxTVAEnum, TypeEcritureEnum

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class EcritureComptable(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "ecritures_comptables"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    type_ecriture: Mapped[TypeEcritureEnum] = mapped_column(
        Enum(TypeEcritureEnum, name="type_ecriture_enum"),
        nullable=False,
    )
    numero_piece: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_piece: Mapped[date | None] = mapped_column(Date, nullable=True)
    tiers: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Comptes exacts Topaze / plan entreprise. Aucun numéro n'est inventé ici.
    compte_tiers: Mapped[str | None] = mapped_column(String(30), nullable=True)
    compte_tva: Mapped[str | None] = mapped_column(String(30), nullable=True)
    compte_ht: Mapped[str | None] = mapped_column(String(30), nullable=True)
    libelle: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # HT / TVA peuvent être absents pour certains documents.
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    taux_tva: Mapped[TauxTVAEnum | None] = mapped_column(
        Enum(TauxTVAEnum, name="taux_tva_enum"),
        nullable=True,
    )
    montant_tva: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    montant_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Devises V2 : représentation originale et valeur comptable initiale.
    # ``montant_ttc`` reste le montant comptable MAD utilisé historiquement.
    devise_originale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="MAD"
    )
    montant_ttc_devise: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    montant_ttc_mad: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    taux_change_initial: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 10), nullable=True
    )
    unite_cotation_initiale: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    date_cours_initial: Mapped[date | None] = mapped_column(Date, nullable=True)
    type_cours_initial: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_cours_initial: Mapped[str | None] = mapped_column(String(50), nullable=True)

    statut_validation: Mapped[StatutValidationEnum] = mapped_column(
        Enum(StatutValidationEnum, name="statut_validation_enum"),
        default=StatutValidationEnum.BROUILLON,
    )

    anomalie_detectee: Mapped[bool] = mapped_column(Boolean, default=False)
    anomalie_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    doublon_potentiel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures_comptables.id"),
        nullable=True,
    )

    saisie_topaze: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="ecritures")
    validated_by_user: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:
        return f"<EcritureComptable {self.type_ecriture} {self.montant_ttc} MAD>"
