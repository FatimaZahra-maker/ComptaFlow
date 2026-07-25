"""
app/models/tache.py

Rappels & Tâches du cabinet -- suivi opérationnel indépendant du
pipeline documentaire (ex: "relancer le client X pour ses pièces
manquantes", "déclarer la TVA du mois", échéances récurrentes).

Rattachement à une entreprise OPTIONNEL : une tâche peut concerner le
cabinet en général (entreprise_id=None) ou une entreprise cliente
précise -- répond au besoin exprimé "le rappel pour quelle entreprise
exactement".
"""
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin
from app.models.enums import StatutTacheEnum, PrioriteTacheEnum, RecurrenceTacheEnum

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise
    from app.models.user import User


class Tache(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "taches"

    entreprise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=True, index=True
    )
    cree_par: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assignee_a: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_echeance: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    statut: Mapped[StatutTacheEnum] = mapped_column(
        Enum(StatutTacheEnum, name="statut_tache_enum"), default=StatutTacheEnum.A_FAIRE
    )
    priorite: Mapped[PrioriteTacheEnum] = mapped_column(
        Enum(PrioriteTacheEnum, name="priorite_tache_enum"), default=PrioriteTacheEnum.NORMALE
    )
    recurrence: Mapped[RecurrenceTacheEnum] = mapped_column(
        Enum(RecurrenceTacheEnum, name="recurrence_tache_enum"), default=RecurrenceTacheEnum.AUCUNE
    )

    entreprise: Mapped["Entreprise | None"] = relationship()
    cree_par_user: Mapped["User"] = relationship(foreign_keys=[cree_par])
    assignee_a_user: Mapped["User | None"] = relationship(foreign_keys=[assignee_a])

    def __repr__(self) -> str:
        return f"<Tache {self.titre} ({self.statut})>"