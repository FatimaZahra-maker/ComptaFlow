"""TVA V2 : périodes, configuration, crédits et régularisations.

Revision ID: b0e5f8a3c792
Revises: a9d4e7f2b681
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b0e5f8a3c792"
down_revision: Union[str, Sequence[str], None] = "a9d4e7f2b681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tva_configurations_entreprise",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("periodicite", sa.String(20), nullable=True),
        sa.Column("prorata_applicable", sa.Boolean(), nullable=True),
        sa.Column("prorata_deduction", sa.Numeric(7, 6), nullable=True),
        sa.Column("retenue_applicable", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cabinet_id", "entreprise_id", name="uq_tva_configuration_tenant"),
    )
    op.create_index("ix_tva_configurations_entreprise_cabinet_id", "tva_configurations_entreprise", ["cabinet_id"])
    op.create_index("ix_tva_configurations_entreprise_entreprise_id", "tva_configurations_entreprise", ["entreprise_id"])

    op.create_table(
        "tva_periodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("annee", sa.Integer(), nullable=False),
        sa.Column("mois", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="provisoire"),
        sa.Column("tva_collectee", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tva_recuperable_charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tva_recuperable_immobilisations", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_anterieur", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("regularisations", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("retenues_tva", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tva_nette", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tva_a_payer", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_a_reporter", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_source_periode_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("calcul_provisoire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validee_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validee_par", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("a_verifier", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("anomalies", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_calcul", sa.String(50), nullable=False, server_default="lignes_comptables_validees"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("mois >= 1 AND mois <= 12", name="ck_tva_periode_mois"),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credit_source_periode_id"], ["tva_periodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validee_par"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cabinet_id", "entreprise_id", "annee", "mois", name="uq_tva_periode_tenant_mois"),
    )
    op.create_index("ix_tva_periodes_cabinet_id", "tva_periodes", ["cabinet_id"])
    op.create_index("ix_tva_periodes_entreprise_id", "tva_periodes", ["entreprise_id"])
    op.create_index("ix_tva_periodes_annee", "tva_periodes", ["annee"])

    op.create_table(
        "tva_regularisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("periode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nature", sa.String(20), nullable=False),
        sa.Column("montant_signe", sa.Numeric(14, 2), nullable=False),
        sa.Column("motif", sa.String(500), nullable=False),
        sa.Column("date_regularisation", sa.Date(), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manuel"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["periode_id"], ["tva_periodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tva_regularisations_cabinet_id", "tva_regularisations", ["cabinet_id"])
    op.create_index("ix_tva_regularisations_entreprise_id", "tva_regularisations", ["entreprise_id"])
    op.create_index("ix_tva_regularisations_periode_id", "tva_regularisations", ["periode_id"])

    op.create_table(
        "tva_credit_utilisations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("periode_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("periode_destination_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("montant_utilise", sa.Numeric(14, 2), nullable=False),
        sa.Column("utilise_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilise_par", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["periode_source_id"], ["tva_periodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["periode_destination_id"], ["tva_periodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["utilise_par"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("periode_source_id", name="uq_tva_credit_source_utilisee"),
        sa.UniqueConstraint("periode_destination_id", name="uq_tva_credit_destination"),
    )
    op.create_index("ix_tva_credit_utilisations_cabinet_id", "tva_credit_utilisations", ["cabinet_id"])
    op.create_index("ix_tva_credit_utilisations_entreprise_id", "tva_credit_utilisations", ["entreprise_id"])


def downgrade() -> None:
    op.drop_table("tva_credit_utilisations")
    op.drop_table("tva_regularisations")
    op.drop_table("tva_periodes")
    op.drop_table("tva_configurations_entreprise")
