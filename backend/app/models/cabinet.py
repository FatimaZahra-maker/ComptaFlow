"""app/models/cabinet.py"""
from typing import List, TYPE_CHECKING

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.entreprise import Entreprise


class Cabinet(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cabinets"

    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    ice: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(500), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users: Mapped[List["User"]] = relationship(back_populates="cabinet")
    entreprises: Mapped[List["Entreprise"]] = relationship(back_populates="cabinet")

    def __repr__(self) -> str:
        return f"<Cabinet {self.nom}>"