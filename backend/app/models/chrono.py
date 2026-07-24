"""app/models/chrono.py"""
import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise
    from app.models.document import Document


class Chrono(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "chronos"
    __table_args__ = (
        UniqueConstraint("entreprise_id", name="uq_chrono_entreprise"),
    )

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(100), default="Chrono principal")

    entreprise: Mapped["Entreprise"] = relationship(back_populates="chronos")
    documents: Mapped[List["Document"]] = relationship(back_populates="chrono")

    def __repr__(self) -> str:
        return f"<Chrono entreprise_id={self.entreprise_id}>"