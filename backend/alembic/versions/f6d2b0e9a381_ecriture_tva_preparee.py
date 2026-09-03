"""Écriture TVA préparée depuis des comptes configurés.

Revision ID: f6d2b0e9a381
Revises: f5c1a9d8e270
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f6d2b0e9a381"
down_revision = "f5c1a9d8e270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in (
        "compte_tva_collectee",
        "compte_tva_recuperable_charges",
        "compte_tva_recuperable_immobilisations",
        "compte_tva_a_payer",
        "compte_credit_tva",
    ):
        op.add_column(
            "tva_configurations_entreprise",
            sa.Column(name, sa.String(length=30), nullable=True),
        )

    op.add_column("tva_periodes", sa.Column("topaze_entered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tva_periodes", sa.Column("topaze_entered_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("tva_periodes", sa.Column("topaze_batch_reference", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_tva_periodes_topaze_entered_by_users",
        "tva_periodes",
        "users",
        ["topaze_entered_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "lignes_comptables",
        sa.Column("tva_periode_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_lignes_comptables_tva_periode",
        "lignes_comptables",
        "tva_periodes",
        ["tva_periode_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_lignes_comptables_tva_periode_id", "lignes_comptables", ["tva_periode_id"])
    op.create_unique_constraint(
        "uq_ligne_comptable_tva_periode_ordre",
        "lignes_comptables",
        ["tva_periode_id", "ordre"],
    )
    op.drop_constraint("ck_ligne_comptable_source_unique", "lignes_comptables", type_="check")
    op.create_check_constraint(
        "ck_ligne_comptable_source_unique",
        "lignes_comptables",
        "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NULL AND tva_periode_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL AND regularisation_cloture_id IS NULL AND tva_periode_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NOT NULL AND tva_periode_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NULL AND tva_periode_id IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ligne_comptable_source_unique", "lignes_comptables", type_="check")
    op.create_check_constraint(
        "ck_ligne_comptable_source_unique",
        "lignes_comptables",
        "((ecriture_id IS NOT NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NOT NULL AND regularisation_cloture_id IS NULL) "
        "OR (ecriture_id IS NULL AND mouvement_bancaire_id IS NULL AND regularisation_cloture_id IS NOT NULL))",
    )
    op.drop_constraint("uq_ligne_comptable_tva_periode_ordre", "lignes_comptables", type_="unique")
    op.drop_index("ix_lignes_comptables_tva_periode_id", table_name="lignes_comptables")
    op.drop_constraint("fk_lignes_comptables_tva_periode", "lignes_comptables", type_="foreignkey")
    op.drop_column("lignes_comptables", "tva_periode_id")

    op.drop_constraint("fk_tva_periodes_topaze_entered_by_users", "tva_periodes", type_="foreignkey")
    op.drop_column("tva_periodes", "topaze_batch_reference")
    op.drop_column("tva_periodes", "topaze_entered_by")
    op.drop_column("tva_periodes", "topaze_entered_at")

    for name in reversed((
        "compte_tva_collectee",
        "compte_tva_recuperable_charges",
        "compte_tva_recuperable_immobilisations",
        "compte_tva_a_payer",
        "compte_credit_tva",
    )):
        op.drop_column("tva_configurations_entreprise", name)
