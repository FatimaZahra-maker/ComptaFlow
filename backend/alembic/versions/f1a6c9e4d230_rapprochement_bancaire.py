"""Ajout du rapprochement bancaire facture/paiement.

Revision ID: f1a6c9e4d230
Revises: d7e3a1f6b420
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f1a6c9e4d230"
down_revision: Union[str, Sequence[str], None] = "d7e3a1f6b420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("mouvements_bancaires")}

    if "ecriture_rapprochee_id" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("ecriture_rapprochee_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_mouvement_ecriture_rapprochee",
            "mouvements_bancaires",
            "ecritures_comptables",
            ["ecriture_rapprochee_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_mouvements_bancaires_ecriture_rapprochee_id",
            "mouvements_bancaires",
            ["ecriture_rapprochee_id"],
            unique=False,
        )

    if "statut_rapprochement" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column(
                "statut_rapprochement",
                sa.String(length=30),
                server_default="non_rapproche",
                nullable=False,
            ),
        )
    if "score_rapprochement" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("score_rapprochement", sa.Numeric(5, 2), nullable=True),
        )
    if "raison_rapprochement" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("raison_rapprochement", sa.String(length=500), nullable=True),
        )
    if "compte_banque" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("compte_banque", sa.String(length=30), nullable=True),
        )
    if "rapprochement_confirme_par" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("rapprochement_confirme_par", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_mouvement_rapprochement_user",
            "mouvements_bancaires",
            "users",
            ["rapprochement_confirme_par"],
            ["id"],
            ondelete="SET NULL",
        )
    if "date_rapprochement" not in columns:
        op.add_column(
            "mouvements_bancaires",
            sa.Column("date_rapprochement", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("mouvements_bancaires")}

    if "date_rapprochement" in columns:
        op.drop_column("mouvements_bancaires", "date_rapprochement")
    if "rapprochement_confirme_par" in columns:
        op.drop_constraint(
            "fk_mouvement_rapprochement_user",
            "mouvements_bancaires",
            type_="foreignkey",
        )
        op.drop_column("mouvements_bancaires", "rapprochement_confirme_par")
    if "compte_banque" in columns:
        op.drop_column("mouvements_bancaires", "compte_banque")
    if "raison_rapprochement" in columns:
        op.drop_column("mouvements_bancaires", "raison_rapprochement")
    if "score_rapprochement" in columns:
        op.drop_column("mouvements_bancaires", "score_rapprochement")
    if "statut_rapprochement" in columns:
        op.drop_column("mouvements_bancaires", "statut_rapprochement")
    if "ecriture_rapprochee_id" in columns:
        op.drop_index(
            "ix_mouvements_bancaires_ecriture_rapprochee_id",
            table_name="mouvements_bancaires",
        )
        op.drop_constraint(
            "fk_mouvement_ecriture_rapprochee",
            "mouvements_bancaires",
            type_="foreignkey",
        )
        op.drop_column("mouvements_bancaires", "ecriture_rapprochee_id")
