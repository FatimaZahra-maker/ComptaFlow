"""Modèle SQLAlchemy des documents importés."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin
from app.models.enums import CategorieDocumentEnum, StatutDocumentEnum, TypeErreurEnum

if TYPE_CHECKING:
    from app.models.chrono import Chrono
    from app.models.ecriture import EcritureComptable
    from app.models.entreprise import Entreprise
    from app.models.mouvement_bancaire import MouvementBancaire
    from app.models.user import User


class Document(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_arbo", "entreprise_id", "annee", "mois", "categorie"),
    )

    entreprise_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=True,
    )
    chrono_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chronos.id", ondelete="CASCADE"),
        nullable=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    annee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mois: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    categorie: Mapped[Optional[CategorieDocumentEnum]] = mapped_column(
        Enum(CategorieDocumentEnum, name="categorie_document_enum"),
        nullable=True,
    )

    nom_fichier_original: Mapped[str] = mapped_column(String(500), nullable=False)
    chemin_stockage: Mapped[str] = mapped_column(String(1000), nullable=False)
    hash_fichier: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    taille_octets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    statut: Mapped[StatutDocumentEnum] = mapped_column(
        Enum(StatutDocumentEnum, name="statut_document_enum"),
        default=StatutDocumentEnum.EN_ATTENTE,
        nullable=False,
    )
    texte_ocr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    donnees_extraites: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    message_erreur: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    type_erreur: Mapped[Optional[TypeErreurEnum]] = mapped_column(
        Enum(TypeErreurEnum, name="type_erreur_enum"),
        nullable=True,
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Statut opérationnel au niveau du document. Il fonctionne aussi pour les
    # relevés bancaires, qui ne possèdent pas toujours d'écriture comptable.
    saisie_topaze: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    entreprise: Mapped[Optional["Entreprise"]] = relationship()
    chrono: Mapped[Optional["Chrono"]] = relationship(back_populates="documents")
    uploaded_by_user: Mapped["User"] = relationship()

    # Les suppressions sont effectuées explicitement par l'API documents pour
    # pouvoir gérer la clé étrangère auto-référencée doublon_potentiel_id.
    ecritures: Mapped[List["EcritureComptable"]] = relationship(
        back_populates="document",
        passive_deletes=True,
    )
    mouvements_bancaires: Mapped[List["MouvementBancaire"]] = relationship(
        back_populates="document",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Document {self.nom_fichier_original} ({self.statut})>"
