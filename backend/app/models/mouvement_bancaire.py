"""Mouvement bancaire extrait d'un relevé.

Banque V2 :
- conserve le mouvement original ;
- permet les règlements simples, partiels et groupés via une table d'allocations ;
- rattache le relevé à un compte bancaire configuré par RIB/IBAN quand possible ;
- distingue les opérations spéciales (acompte, frais, virement interne, autre) ;
- n'invente jamais un compte comptable exact.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CabinetScopedMixin, TimestampMixin, UUIDMixin
from app.models.enums import TypeMouvementBancaireEnum

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.ecriture import EcritureComptable
    from app.models.user import User


class MouvementBancaire(Base, UUIDMixin, TimestampMixin, CabinetScopedMixin):
    __tablename__ = "mouvements_bancaires"

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

    date_operation: Mapped[date] = mapped_column(Date, nullable=False)
    libelle: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    type_mouvement: Mapped[TypeMouvementBancaireEnum] = mapped_column(
        Enum(TypeMouvementBancaireEnum, name="type_mouvement_enum"),
        nullable=False,
    )
    # montant = montant comptable MAD utilisé par le journal Banque.
    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    solde_apres_operation: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # ------------------------------------------------------------
    # DEVISE / CONVERSION BAM
    # ------------------------------------------------------------
    devise_originale: Mapped[str] = mapped_column(
        String(10), nullable=False, default="MAD"
    )
    montant_devise: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    montant_mad: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    # Valeur BAM théorique distincte du montant MAD réellement débité/crédité.
    montant_mad_theorique: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    # mad | banque | bam | indisponible
    montant_mad_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="mad"
    )
    taux_change: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 10), nullable=True
    )
    type_cours_change: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_cours_change: Mapped[date | None] = mapped_column(Date, nullable=True)
    unite_cotation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_cours_change: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ------------------------------------------------------------
    # COMPTE BANCAIRE / NATURE V2
    # ------------------------------------------------------------
    compte_bancaire_entreprise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comptes_bancaires_entreprise.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # reglement_facture | acompte | frais_bancaire | virement_interne | autre
    nature_operation: Mapped[str] = mapped_column(
        String(30), nullable=False, default="reglement_facture"
    )
    # Pour frais/acompte/autre : compte exact validé manuellement.
    compte_contrepartie: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Pour les virements internes : mouvement opposé sur l'autre compte bancaire.
    mouvement_lie_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mouvements_bancaires.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------
    # RAPPROCHEMENT FACTURE / PAIEMENT
    # ------------------------------------------------------------
    # Champ historique conservé pour compatibilité UI/API V1. Banque V2 utilise
    # la table rapprochements_bancaires_allocations comme source de vérité.
    ecriture_rapprochee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ecritures_comptables.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # non_rapproche | propose | automatique | confirme | ambigu
    statut_rapprochement: Mapped[str] = mapped_column(
        String(30), nullable=False, default="non_rapproche"
    )
    # simple | partiel | groupe | special
    mode_rapprochement: Mapped[str] = mapped_column(
        String(20), nullable=False, default="simple"
    )
    score_rapprochement: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    raison_rapprochement: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Compte bancaire exact du plan de l'entreprise.
    compte_banque: Mapped[str | None] = mapped_column(String(30), nullable=True)

    rapprochement_confirme_par: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    date_rapprochement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="mouvements_bancaires")
    ecriture_rapprochee: Mapped["EcritureComptable | None"] = relationship(
        foreign_keys=[ecriture_rapprochee_id]
    )
    confirme_par_user: Mapped["User | None"] = relationship(
        foreign_keys=[rapprochement_confirme_par]
    )
    mouvement_lie: Mapped["MouvementBancaire | None"] = relationship(
        "MouvementBancaire",
        foreign_keys=[mouvement_lie_id],
        remote_side="MouvementBancaire.id",
        post_update=True,
    )

    def __repr__(self) -> str:
        return (
            f"<MouvementBancaire {self.date_operation} - "
            f"{self.type_mouvement} {self.montant}>"
        )
