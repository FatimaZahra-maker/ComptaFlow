"""ajout type_erreur et error_code sur documents

Revision ID: 18e58386fcfa
Revises: f29924d2e6e1
Create Date: 2026-07-21 01:09:48.222584

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "18e58386fcfa"
down_revision: Union[str, Sequence[str], None] = "f29924d2e6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Le type ENUM PostgreSQL doit être créé explicitement
    # avant toute colonne qui l'utilise.
    type_erreur_enum = postgresql.ENUM(
        "TRANSITOIRE",
        "DEFINITIVE",
        name="type_erreur_enum",
    )
    type_erreur_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "documents",
        sa.Column(
            "type_erreur",
            type_erreur_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "documents",
        sa.Column(
            "error_code",
            sa.String(length=50),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("documents", "error_code")
    op.drop_column("documents", "type_erreur")

    # Suppression du type ENUM PostgreSQL
    type_erreur_enum = postgresql.ENUM(
        "TRANSITOIRE",
        "DEFINITIVE",
        name="type_erreur_enum",
    )
    type_erreur_enum.drop(op.get_bind(), checkfirst=True)