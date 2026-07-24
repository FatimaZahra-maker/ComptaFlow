"""app/models/user.py"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin, TimestampMixin, CabinetScopedMixin
from app.models.enums import RoleEnum

if TYPE_CHECKING:
    from app.models.cabinet import Cabinet


class User(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, name="role_enum"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cabinet: Mapped["Cabinet"] = relationship(back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"