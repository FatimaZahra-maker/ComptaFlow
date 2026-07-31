"""Ajout de saisie_topaze sur les documents.

Revision ID: a7c9e2b4d610
Revises: 65a34d21d0e5
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e2b4d610"
down_revision: Union[str, Sequence[str], None] = "65a34d21d0e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "saisie_topaze",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Reprend le statut déjà présent sur l'écriture quand une facture avait
    # été marquée comme saisie avant l'ajout du champ au niveau document.
    op.execute(
        """
        UPDATE documents AS d
        SET saisie_topaze = TRUE
        WHERE EXISTS (
            SELECT 1
            FROM ecritures_comptables AS e
            WHERE e.document_id = d.id
              AND e.saisie_topaze = TRUE
        )
        """
    )


def downgrade() -> None:
    op.drop_column("documents", "saisie_topaze")