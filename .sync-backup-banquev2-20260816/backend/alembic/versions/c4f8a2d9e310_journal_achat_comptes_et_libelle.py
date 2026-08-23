"""journal achat comptes et libelle

Revision ID: c4f8a2d9e310
Revises: b91f2d7c4a80
Create Date: 2026-08-13 01:15:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f8a2d9e310"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "b91f2d7c4a80"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.add_column(
        "ecritures_comptables",
        sa.Column(
            "compte_tiers",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "ecritures_comptables",
        sa.Column(
            "compte_tva",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "ecritures_comptables",
        sa.Column(
            "compte_ht",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "ecritures_comptables",
        sa.Column(
            "libelle",
            sa.String(length=500),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "ecritures_comptables",
        "libelle",
    )

    op.drop_column(
        "ecritures_comptables",
        "compte_ht",
    )

    op.drop_column(
        "ecritures_comptables",
        "compte_tva",
    )

    op.drop_column(
        "ecritures_comptables",
        "compte_tiers",
    )