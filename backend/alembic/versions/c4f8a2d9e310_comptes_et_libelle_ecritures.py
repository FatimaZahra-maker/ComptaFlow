"""Ajout des comptes tiers/TVA/HT et du libellé aux écritures.

Revision ID: c4f8a2d9e310
Revises: b91f2d7c4a80
Create Date: 2026-07-30

Migration volontairement idempotente : elle peut être présente dans un projet
restauré alors que les colonnes ont déjà été ajoutées sur une base existante.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a2d9e310"
down_revision: Union[str, Sequence[str], None] = "b91f2d7c4a80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = (
    ("compte_tiers", sa.String(length=30)),
    ("compte_tva", sa.String(length=30)),
    ("compte_ht", sa.String(length=30)),
    ("libelle", sa.String(length=500)),
)


def _column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns("ecritures_comptables")}


def upgrade() -> None:
    existing = _column_names()
    for name, type_ in _COLUMNS:
        if name not in existing:
            op.add_column(
                "ecritures_comptables",
                sa.Column(name, type_, nullable=True),
            )


def downgrade() -> None:
    existing = _column_names()
    for name, _type in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("ecritures_comptables", name)
