"""Ajout du plan comptable exact par entreprise.

Revision ID: d7e3a1f6b420
Revises: c4f8a2d9e310
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d7e3a1f6b420"
down_revision: Union[str, Sequence[str], None] = "c4f8a2d9e310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("comptes_comptables_entreprise"):
        return

    op.create_table(
        "comptes_comptables_entreprise",
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("numero_compte", sa.String(length=30), nullable=False),
        sa.Column("libelle", sa.String(length=255), nullable=False),
        sa.Column("famille_cgnc", sa.String(length=20), nullable=True),
        sa.Column("type_usage", sa.String(length=30), nullable=False),
        sa.Column("nature_comptable", sa.String(length=100), nullable=True),
        sa.Column("tiers_nom", sa.String(length=255), nullable=True),
        sa.Column("tiers_normalise", sa.String(length=255), nullable=True),
        sa.Column("est_divers", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("source", sa.String(length=50), server_default="manuel", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["cabinet_id"],
            ["cabinets.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entreprise_id"],
            ["entreprises.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cabinet_id",
            "entreprise_id",
            "numero_compte",
            name="uq_compte_comptable_entreprise_numero",
        ),
    )

    op.create_index(
        "ix_comptes_comptables_entreprise_cabinet_id",
        "comptes_comptables_entreprise",
        ["cabinet_id"],
        unique=False,
    )
    op.create_index(
        "ix_comptes_comptables_entreprise_entreprise_id",
        "comptes_comptables_entreprise",
        ["entreprise_id"],
        unique=False,
    )
    op.create_index(
        "ix_compte_comptable_entreprise_famille",
        "comptes_comptables_entreprise",
        ["cabinet_id", "entreprise_id", "famille_cgnc"],
        unique=False,
    )
    op.create_index(
        "ix_compte_comptable_entreprise_tiers",
        "comptes_comptables_entreprise",
        ["cabinet_id", "entreprise_id", "type_usage", "tiers_normalise"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("comptes_comptables_entreprise"):
        return

    op.drop_index(
        "ix_compte_comptable_entreprise_tiers",
        table_name="comptes_comptables_entreprise",
    )
    op.drop_index(
        "ix_compte_comptable_entreprise_famille",
        table_name="comptes_comptables_entreprise",
    )
    op.drop_index(
        "ix_comptes_comptables_entreprise_entreprise_id",
        table_name="comptes_comptables_entreprise",
    )
    op.drop_index(
        "ix_comptes_comptables_entreprise_cabinet_id",
        table_name="comptes_comptables_entreprise",
    )
    op.drop_table("comptes_comptables_entreprise")
