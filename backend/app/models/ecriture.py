"""app/models/ecriture.py"""
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Enum, ForeignKey, Numeric, Date, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin
from app.models.enums import TypeEcritureEnum, TauxTVAEnum, StatutValidationEnum

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class EcritureComptable(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "ecritures_comptables"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    validated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    type_ecriture: Mapped[TypeEcritureEnum] = mapped_column(
        Enum(TypeEcritureEnum, name="type_ecriture_enum"), nullable=False
    )
    numero_piece: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_piece: Mapped[date | None] = mapped_column(Date, nullable=True)
    tiers: Mapped[str | None] = mapped_column(String(255), nullable=True)  # nom fournisseur/client

    # --- MODIFICATIONS ICI : HT, Taux TVA et TVA deviennent optionnels (pour la CNSS etc.) ---
    montant_ht: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    taux_tva: Mapped[TauxTVAEnum | None] = mapped_column(Enum(TauxTVAEnum, name="taux_tva_enum"), nullable=True)
    montant_tva: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    
    # Le TTC reste obligatoire (Total facture, total à payer CNSS, etc.)
    montant_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    statut_validation: Mapped[StatutValidationEnum] = mapped_column(
        Enum(StatutValidationEnum, name="statut_validation_enum"),
        default=StatutValidationEnum.BROUILLON,
    )

    # --- Vérifications automatiques (TVA, doublons) ---
    anomalie_detectee: Mapped[bool] = mapped_column(Boolean, default=False)
    anomalie_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    doublon_potentiel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ecritures_comptables.id"), nullable=True
    )

    # --- Suivi de saisie dans le logiciel comptable externe (Topaze) ---
    # Champ opérationnel : coché par le comptable une fois la ligne
    # ressaisie manuellement dans Topaze, indépendant du statut_validation
    # (une écriture peut être validée mais pas encore saisie ailleurs).
    saisie_topaze: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="ecritures")
    validated_by_user: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:
        return f"<EcritureComptable {self.type_ecriture} {self.montant_ttc} MAD>"