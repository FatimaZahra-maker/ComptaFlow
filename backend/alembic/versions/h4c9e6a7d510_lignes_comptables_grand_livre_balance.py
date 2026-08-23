"""Lignes Débit/Crédit, Grand Livre et Balance.

Revision ID: h4c9e6a7d510
Revises: g3b8d2f5c640
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h4c9e6a7d510"
down_revision: Union[str, Sequence[str], None] = "g3b8d2f5c640"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "lignes_comptables" in set(inspector.get_table_names()):
        return

    op.create_table(
        "lignes_comptables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ecriture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mouvement_bancaire_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("date_ecriture", sa.Date(), nullable=False),
        sa.Column("journal", sa.String(length=10), nullable=False),
        sa.Column("numero_piece", sa.String(length=100), nullable=True),
        sa.Column("compte", sa.String(length=30), nullable=False),
        sa.Column("libelle", sa.String(length=500), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("origine", sa.String(length=20), nullable=False),
        sa.Column("est_validee", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name="ck_ligne_comptable_montants_positifs",
        ),
        sa.CheckConstraint(
            "((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))",
            name="ck_ligne_comptable_un_seul_sens",
        ),
        sa.CheckConstraint(
            "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL) "
            "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL))",
            name="ck_ligne_comptable_source_unique",
        ),
        sa.ForeignKeyConstraint(
            ["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ecriture_id"], ["ecritures_comptables.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mouvement_bancaire_id"], ["mouvements_bancaires.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ecriture_id", "ordre", name="uq_ligne_comptable_ecriture_ordre"
        ),
        sa.UniqueConstraint(
            "mouvement_bancaire_id",
            "ordre",
            name="uq_ligne_comptable_mouvement_ordre",
        ),
    )

    op.create_index(
        "ix_lignes_comptables_cabinet_id",
        "lignes_comptables",
        ["cabinet_id"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_comptables_entreprise_id",
        "lignes_comptables",
        ["entreprise_id"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_comptables_ecriture_id",
        "lignes_comptables",
        ["ecriture_id"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_comptables_mouvement_bancaire_id",
        "lignes_comptables",
        ["mouvement_bancaire_id"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_comptables_date_ecriture",
        "lignes_comptables",
        ["date_ecriture"],
        unique=False,
    )
    op.create_index(
        "ix_lignes_comptables_compte",
        "lignes_comptables",
        ["compte"],
        unique=False,
    )
    op.create_index(
        "ix_ligne_comptable_grand_livre",
        "lignes_comptables",
        ["cabinet_id", "entreprise_id", "date_ecriture", "compte"],
        unique=False,
    )
    op.create_index(
        "ix_ligne_comptable_validation",
        "lignes_comptables",
        ["cabinet_id", "entreprise_id", "est_validee"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "lignes_comptables" not in set(sa.inspect(bind).get_table_names()):
        return
    op.drop_table("lignes_comptables")
