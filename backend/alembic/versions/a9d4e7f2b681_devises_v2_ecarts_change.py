"""Devises V2 : valeurs initiales, règlements et écarts de change.

Revision ID: a9d4e7f2b681
Revises: c8a1d2e3f470
Create Date: 2026-08-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a9d4e7f2b681"
down_revision: Union[str, Sequence[str], None] = "c8a1d2e3f470"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ecritures_comptables") as batch:
        batch.add_column(sa.Column("devise_originale", sa.String(10), nullable=False, server_default="MAD"))
        batch.add_column(sa.Column("montant_ttc_devise", sa.Numeric(18, 6), nullable=True))
        batch.add_column(sa.Column("montant_ttc_mad", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("taux_change_initial", sa.Numeric(20, 10), nullable=True))
        batch.add_column(sa.Column("unite_cotation_initiale", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("date_cours_initial", sa.Date(), nullable=True))
        batch.add_column(sa.Column("type_cours_initial", sa.String(30), nullable=True))
        batch.add_column(sa.Column("source_cours_initial", sa.String(50), nullable=True))

    op.execute(
        """
        UPDATE ecritures_comptables
        SET devise_originale = 'MAD',
            montant_ttc_devise = montant_ttc,
            montant_ttc_mad = montant_ttc,
            unite_cotation_initiale = 1
        """
    )

    with op.batch_alter_table("mouvements_bancaires") as batch:
        batch.add_column(sa.Column("montant_mad_theorique", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("montant_mad_source", sa.String(20), nullable=False, server_default="mad"))

    op.execute(
        """
        UPDATE mouvements_bancaires
        SET montant_mad_theorique = montant_mad,
            montant_mad_source = CASE
                WHEN devise_originale IS NULL OR devise_originale = 'MAD' THEN 'mad'
                WHEN montant_mad IS NOT NULL THEN 'bam'
                ELSE 'indisponible'
            END
        """
    )

    with op.batch_alter_table("rapprochements_bancaires_allocations") as batch:
        batch.add_column(sa.Column("montant_devise_affecte", sa.Numeric(18, 6), nullable=True))
        batch.add_column(sa.Column("valeur_comptable_mad", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("montant_reglement_mad", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("ecart_change_mad", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("nature_ecart_change", sa.String(20), nullable=True))
        batch.add_column(sa.Column("compte_ecart_change", sa.String(30), nullable=True))
        batch.add_column(sa.Column("statut_ecart_change", sa.String(20), nullable=False, server_default="non_requis"))
        batch.add_column(sa.Column("raison_ecart_change", sa.String(500), nullable=True))

    op.execute(
        """
        UPDATE rapprochements_bancaires_allocations
        SET valeur_comptable_mad = montant_affecte,
            montant_reglement_mad = montant_affecte,
            ecart_change_mad = 0,
            nature_ecart_change = 'sans_ecart',
            statut_ecart_change = 'non_requis'
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("rapprochements_bancaires_allocations") as batch:
        for name in (
            "raison_ecart_change",
            "statut_ecart_change",
            "compte_ecart_change",
            "nature_ecart_change",
            "ecart_change_mad",
            "montant_reglement_mad",
            "valeur_comptable_mad",
            "montant_devise_affecte",
        ):
            batch.drop_column(name)

    with op.batch_alter_table("mouvements_bancaires") as batch:
        batch.drop_column("montant_mad_source")
        batch.drop_column("montant_mad_theorique")

    with op.batch_alter_table("ecritures_comptables") as batch:
        for name in (
            "source_cours_initial",
            "type_cours_initial",
            "date_cours_initial",
            "unite_cotation_initiale",
            "taux_change_initial",
            "montant_ttc_mad",
            "montant_ttc_devise",
            "devise_originale",
        ):
            batch.drop_column(name)
