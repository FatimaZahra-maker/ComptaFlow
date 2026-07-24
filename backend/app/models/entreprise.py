"""app/models/entreprise.py"""
from typing import List, TYPE_CHECKING

from sqlalchemy import String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin

if TYPE_CHECKING:
    from app.models.cabinet import Cabinet
    from app.models.chrono import Chrono


class Entreprise(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "entreprises"
    __table_args__ = (
        # Une ICE = une seule entreprise par cabinet -> permet la
        # déduplication automatique lors de l'identification par l'IA.
        UniqueConstraint("cabinet_id", "ice", name="uq_entreprise_cabinet_ice"),
    )

    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    ice: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    identifiant_fiscal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    forme_juridique: Mapped[str | None] = mapped_column(String(50), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # True si créée automatiquement par le pipeline IA (pas encore
    # vérifiée par un humain) -> permet d'afficher un badge "à vérifier".
    creee_automatiquement: Mapped[bool] = mapped_column(Boolean, default=False)

    cabinet: Mapped["Cabinet"] = relationship(back_populates="entreprises")
    chronos: Mapped[List["Chrono"]] = relationship(back_populates="entreprise")

    def __repr__(self) -> str:
        return f"<Entreprise {self.nom} (ICE={self.ice})>"