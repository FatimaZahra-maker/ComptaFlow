"""Création réelle de la table mouvements_bancaires.

Revision ID: b91f2d7c4a80
Revises: a7c9e2b4d610
Create Date: 2026-07-28

La migration 1cd6f5a62909 portait le nom « mouvements_bancaires » mais
ne créait pas la table. Le modèle SQLAlchemy et les API l'utilisaient donc
alors que PostgreSQL ne la connaissait pas, ce qui bloquait Banque,
Vérifier, Retraiter et Supprimer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b91f2d7c4a80"
down_revision: Union[str, Sequence[str], None] = "a7c9e2b4d610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # La migration reste sûre si la table a déjà été créée manuellement.
    if inspector.has_table("mouvements_bancaires"):
        return

    type_mouvement_enum = postgresql.ENUM(
        "DEBIT",
        "CREDIT",
        name="type_mouvement_enum",
        create_type=False,
    )

    # Crée le type PostgreSQL seulement s'il n'existe pas encore.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'type_mouvement_enum'
            ) THEN
                CREATE TYPE type_mouvement_enum AS ENUM ('DEBIT', 'CREDIT');
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "mouvements_bancaires",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date_operation", sa.Date(), nullable=False),
        sa.Column("libelle", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("type_mouvement", type_mouvement_enum, nullable=False),
        sa.Column("montant", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("solde_apres_operation", sa.Numeric(precision=12, scale=2), nullable=True),
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
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entreprise_id"],
            ["entreprises.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_mouvements_bancaires_cabinet_id",
        "mouvements_bancaires",
        ["cabinet_id"],
        unique=False,
    )
    op.create_index(
        "ix_mouvements_bancaires_document_id",
        "mouvements_bancaires",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_mouvements_bancaires_entreprise_id",
        "mouvements_bancaires",
        ["entreprise_id"],
        unique=False,
    )
    op.create_index(
        "ix_mouvements_bancaires_date_operation",
        "mouvements_bancaires",
        ["date_operation"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("mouvements_bancaires"):
        op.drop_index(
            "ix_mouvements_bancaires_date_operation",
            table_name="mouvements_bancaires",
        )
        op.drop_index(
            "ix_mouvements_bancaires_entreprise_id",
            table_name="mouvements_bancaires",
        )
        op.drop_index(
            "ix_mouvements_bancaires_document_id",
            table_name="mouvements_bancaires",
        )
        op.drop_index(
            "ix_mouvements_bancaires_cabinet_id",
            table_name="mouvements_bancaires",
        )
        op.drop_table("mouvements_bancaires")

    op.execute("DROP TYPE IF EXISTS type_mouvement_enum")