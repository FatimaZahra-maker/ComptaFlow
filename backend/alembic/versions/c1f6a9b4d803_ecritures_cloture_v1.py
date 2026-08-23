"""Ecritures de cloture V1.

Revision ID: c1f6a9b4d803
Revises: b0e5f8a3c792
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c1f6a9b4d803"
down_revision: Union[str, Sequence[str], None] = "b0e5f8a3c792"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regularisations_cloture",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercice", sa.Integer(), nullable=False),
        sa.Column("date_ecriture", sa.Date(), nullable=False),
        sa.Column("type_regularisation", sa.String(40), nullable=False),
        sa.Column("libelle", sa.String(500), nullable=False),
        sa.Column("montant", sa.Numeric(14, 2), nullable=False),
        sa.Column("compte_debit", sa.String(30), nullable=True),
        sa.Column("compte_credit", sa.String(30), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manuel"),
        sa.Column("anomalies", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("donnees_calcul", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("a_extourner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("date_extourne", sa.Date(), nullable=True),
        sa.Column("report_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("motif_annulation", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_source_id"], ["regularisations_cloture.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_source_id", name="uq_regularisation_cloture_report_source"),
    )
    op.create_index("ix_regularisations_cloture_cabinet_id", "regularisations_cloture", ["cabinet_id"])
    op.create_index("ix_regularisations_cloture_entreprise_id", "regularisations_cloture", ["entreprise_id"])
    op.create_index("ix_regularisations_cloture_exercice", "regularisations_cloture", ["exercice"])

    op.add_column("lignes_comptables", sa.Column("regularisation_cloture_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_lignes_comptables_regularisation_cloture", "lignes_comptables", "regularisations_cloture",
        ["regularisation_cloture_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_lignes_comptables_regularisation_cloture_id", "lignes_comptables", ["regularisation_cloture_id"])
    op.create_unique_constraint(
        "uq_ligne_comptable_cloture_ordre", "lignes_comptables", ["regularisation_cloture_id", "ordre"]
    )
    op.drop_constraint("ck_ligne_comptable_source_unique", "lignes_comptables", type_="check")
    op.create_check_constraint(
        "ck_ligne_comptable_source_unique", "lignes_comptables",
        "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL AND regularisation_cloture_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ligne_comptable_source_unique", "lignes_comptables", type_="check")
    op.create_check_constraint(
        "ck_ligne_comptable_source_unique", "lignes_comptables",
        "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL))",
    )
    op.drop_constraint("uq_ligne_comptable_cloture_ordre", "lignes_comptables", type_="unique")
    op.drop_index("ix_lignes_comptables_regularisation_cloture_id", table_name="lignes_comptables")
    op.drop_constraint("fk_lignes_comptables_regularisation_cloture", "lignes_comptables", type_="foreignkey")
    op.drop_column("lignes_comptables", "regularisation_cloture_id")
    op.drop_table("regularisations_cloture")
