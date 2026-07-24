"""app/models/document.py"""
import uuid
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Enum, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin
from app.models.enums import CategorieDocumentEnum, StatutDocumentEnum, TypeErreurEnum

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise
    from app.models.chrono import Chrono
    from app.models.user import User
    from app.models.ecriture import EcritureComptable


class Document(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_arbo", "entreprise_id", "annee", "mois", "categorie"),
    )

    entreprise_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=True
    )
    chrono_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chronos.id", ondelete="CASCADE"), nullable=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    annee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mois: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    categorie: Mapped[Optional[CategorieDocumentEnum]] = mapped_column(
        Enum(CategorieDocumentEnum, name="categorie_document_enum"), nullable=True
    )

    nom_fichier_original: Mapped[str] = mapped_column(String(500), nullable=False)
    chemin_stockage: Mapped[str] = mapped_column(String(1000), nullable=False)
    hash_fichier: Mapped[str] = mapped_column(String(64), index=True)
    taille_octets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    statut: Mapped[StatutDocumentEnum] = mapped_column(
        Enum(StatutDocumentEnum, name="statut_document_enum"),
        default=StatutDocumentEnum.EN_ATTENTE,
    )
    texte_ocr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    donnees_extraites: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    message_erreur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- SPRINT 1.1 : catégorisation de l'erreur, pour le dashboard ---
    type_erreur: Mapped[Optional[TypeErreurEnum]] = mapped_column(
        Enum(TypeErreurEnum, name="type_erreur_enum"), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    entreprise: Mapped[Optional["Entreprise"]] = relationship()
    chrono: Mapped[Optional["Chrono"]] = relationship(back_populates="documents")
    uploaded_by_user: Mapped["User"] = relationship()
    ecritures: Mapped[List["EcritureComptable"]] = relationship(back_populates="document")

    def __repr__(self) -> str:
        return f"<Document {self.nom_fichier_original} ({self.statut})>"