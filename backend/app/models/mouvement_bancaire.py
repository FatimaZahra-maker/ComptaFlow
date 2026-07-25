"""app/models/mouvement_bancaire.py"""
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Enum, ForeignKey, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin
from app.models.enums import TypeMouvementBancaireEnum

if TYPE_CHECKING:
    from app.models.document import Document


class MouvementBancaire(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "mouvements_bancaires"

    # Lien vers le document PDF original (le relevé)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date_operation: Mapped[date] = mapped_column(Date, nullable=False)
    libelle: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    type_mouvement: Mapped[TypeMouvementBancaireEnum] = mapped_column(
        Enum(TypeMouvementBancaireEnum, name="type_mouvement_enum"), nullable=False
    )
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    solde_apres_operation: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="mouvements_bancaires")

    def __repr__(self) -> str:
        return f"<MouvementBancaire {self.date_operation} - {self.type_mouvement} {self.montant}>"