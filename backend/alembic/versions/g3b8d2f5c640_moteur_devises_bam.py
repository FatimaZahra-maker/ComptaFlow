"""Moteur devises Bank Al-Maghrib.

Revision ID: g3b8d2f5c640
Revises: f1a6c9e4d230
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "g3b8d2f5c640"
down_revision: Union[str, Sequence[str], None] = "f1a6c9e4d230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "taux_change_bam" not in tables:
        op.create_table(
            "taux_change_bam",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("date_cours", sa.Date(), nullable=False),
            sa.Column("devise", sa.String(length=10), nullable=False),
            sa.Column("unite_cotation", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("libelle_bam", sa.String(length=120), nullable=False),
            sa.Column("cours_achat", sa.Numeric(20, 10), nullable=False),
            sa.Column("cours_vente", sa.Numeric(20, 10), nullable=False),
            sa.Column(
                "source",
                sa.String(length=50),
                nullable=False,
                server_default="bam_billets_etrangers",
            ),
            sa.Column("source_url", sa.String(length=500), nullable=False),
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
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "date_cours",
                "devise",
                "source",
                name="uq_taux_change_bam_date_devise_source",
            ),
        )
        op.create_index(
            "ix_taux_change_bam_date_cours",
            "taux_change_bam",
            ["date_cours"],
            unique=False,
        )
        op.create_index(
            "ix_taux_change_bam_devise",
            "taux_change_bam",
            ["devise"],
            unique=False,
        )

    movement_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("mouvements_bancaires")
    }

    additions = (
        ("devise_originale", sa.String(length=10), False, "MAD"),
        ("montant_devise", sa.Numeric(18, 6), True, None),
        ("montant_mad", sa.Numeric(14, 2), True, None),
        ("taux_change", sa.Numeric(20, 10), True, None),
        ("type_cours_change", sa.String(length=30), True, None),
        ("date_cours_change", sa.Date(), True, None),
        ("unite_cotation", sa.Integer(), True, None),
        ("source_cours_change", sa.String(length=50), True, None),
    )

    for name, column_type, nullable, server_default in additions:
        if name in movement_columns:
            continue
        kwargs = {"nullable": nullable}
        if server_default is not None:
            kwargs["server_default"] = server_default
        op.add_column(
            "mouvements_bancaires",
            sa.Column(name, column_type, **kwargs),
        )

    # Les anciennes lignes étaient en MAD : on initialise explicitement
    # les deux représentations afin de garder l'historique cohérent.
    op.execute(
        """
        UPDATE mouvements_bancaires
        SET devise_originale = COALESCE(devise_originale, 'MAD'),
            montant_devise = COALESCE(montant_devise, montant),
            montant_mad = COALESCE(montant_mad, montant)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    movement_columns = {
        column["name"]
        for column in inspector.get_columns("mouvements_bancaires")
    }

    for name in (
        "source_cours_change",
        "unite_cotation",
        "date_cours_change",
        "type_cours_change",
        "taux_change",
        "montant_mad",
        "montant_devise",
        "devise_originale",
    ):
        if name in movement_columns:
            op.drop_column("mouvements_bancaires", name)

    if "taux_change_bam" in set(sa.inspect(bind).get_table_names()):
        op.drop_index("ix_taux_change_bam_devise", table_name="taux_change_bam")
        op.drop_index("ix_taux_change_bam_date_cours", table_name="taux_change_bam")
        op.drop_table("taux_change_bam")
