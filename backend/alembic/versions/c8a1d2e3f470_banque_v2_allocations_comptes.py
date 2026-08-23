"""Banque V2 : allocations partielles/groupées et comptes bancaires.

Revision ID: c8a1d2e3f470
Revises: h4c9e6a7d510
Create Date: 2026-08-16
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c8a1d2e3f470"
down_revision: Union[str, Sequence[str], None] = "h4c9e6a7d510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "comptes_bancaires_entreprise" not in tables:
        op.create_table(
            "comptes_bancaires_entreprise",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("libelle", sa.String(length=120), nullable=False),
            sa.Column("banque_nom", sa.String(length=120), nullable=True),
            sa.Column("rib", sa.String(length=64), nullable=True),
            sa.Column("iban", sa.String(length=64), nullable=True),
            sa.Column("bic_swift", sa.String(length=24), nullable=True),
            sa.Column("devise", sa.String(length=10), nullable=False, server_default="MAD"),
            sa.Column("numero_compte_comptable", sa.String(length=30), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_comptes_bancaires_entreprise_cabinet_id", "comptes_bancaires_entreprise", ["cabinet_id"])
        op.create_index("ix_comptes_bancaires_entreprise_entreprise_id", "comptes_bancaires_entreprise", ["entreprise_id"])
        op.create_index(
            "ix_compte_bancaire_entreprise_identification",
            "comptes_bancaires_entreprise",
            ["cabinet_id", "entreprise_id", "is_active"],
        )

    if "rapprochements_bancaires_allocations" not in tables:
        op.create_table(
            "rapprochements_bancaires_allocations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("mouvement_bancaire_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("ecriture_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("montant_affecte", sa.Numeric(14, 2), nullable=False),
            sa.Column("statut", sa.String(length=30), nullable=False, server_default="propose"),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("raison", sa.String(length=500), nullable=True),
            sa.Column("confirme_par", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("date_confirmation", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["mouvement_bancaire_id"], ["mouvements_bancaires.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["ecriture_id"], ["ecritures_comptables.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["confirme_par"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "mouvement_bancaire_id",
                "ecriture_id",
                name="uq_rapprochement_bancaire_mouvement_ecriture",
            ),
        )
        op.create_index("ix_rapprochements_bancaires_allocations_cabinet_id", "rapprochements_bancaires_allocations", ["cabinet_id"])
        op.create_index("ix_rapprochements_bancaires_allocations_entreprise_id", "rapprochements_bancaires_allocations", ["entreprise_id"])
        op.create_index("ix_rapprochements_bancaires_allocations_mouvement_bancaire_id", "rapprochements_bancaires_allocations", ["mouvement_bancaire_id"])
        op.create_index("ix_rapprochements_bancaires_allocations_ecriture_id", "rapprochements_bancaires_allocations", ["ecriture_id"])
        op.create_index(
            "ix_rapprochement_bancaire_ecriture_statut",
            "rapprochements_bancaires_allocations",
            ["cabinet_id", "entreprise_id", "ecriture_id", "statut"],
        )

    cols = _columns("mouvements_bancaires")
    with op.batch_alter_table("mouvements_bancaires") as batch:
        if "compte_bancaire_entreprise_id" not in cols:
            batch.add_column(sa.Column("compte_bancaire_entreprise_id", postgresql.UUID(as_uuid=True), nullable=True))
            batch.create_foreign_key(
                "fk_mouvement_compte_bancaire_entreprise",
                "comptes_bancaires_entreprise",
                ["compte_bancaire_entreprise_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "nature_operation" not in cols:
            batch.add_column(sa.Column("nature_operation", sa.String(length=30), nullable=False, server_default="reglement_facture"))
        if "compte_contrepartie" not in cols:
            batch.add_column(sa.Column("compte_contrepartie", sa.String(length=30), nullable=True))
        if "mouvement_lie_id" not in cols:
            batch.add_column(sa.Column("mouvement_lie_id", postgresql.UUID(as_uuid=True), nullable=True))
            batch.create_foreign_key(
                "fk_mouvement_bancaire_mouvement_lie",
                "mouvements_bancaires",
                ["mouvement_lie_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "mode_rapprochement" not in cols:
            batch.add_column(sa.Column("mode_rapprochement", sa.String(length=20), nullable=False, server_default="simple"))

    # indexes after columns exist
    inspector = sa.inspect(bind)
    existing_indexes = {i["name"] for i in inspector.get_indexes("mouvements_bancaires")}
    if "ix_mouvements_bancaires_compte_bancaire_entreprise_id" not in existing_indexes:
        op.create_index(
            "ix_mouvements_bancaires_compte_bancaire_entreprise_id",
            "mouvements_bancaires",
            ["compte_bancaire_entreprise_id"],
        )
    if "ix_mouvements_bancaires_mouvement_lie_id" not in existing_indexes:
        op.create_index(
            "ix_mouvements_bancaires_mouvement_lie_id",
            "mouvements_bancaires",
            ["mouvement_lie_id"],
        )

    # Compatibilité avec Banque V1 : recopier les rapprochements simples déjà
    # confirmés/automatiques dans la nouvelle table d'allocations. UUID généré
    # en Python pour ne dépendre d'aucune extension PostgreSQL.
    mouvements = sa.table(
        "mouvements_bancaires",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("cabinet_id", postgresql.UUID(as_uuid=True)),
        sa.column("entreprise_id", postgresql.UUID(as_uuid=True)),
        sa.column("ecriture_rapprochee_id", postgresql.UUID(as_uuid=True)),
        sa.column("montant", sa.Numeric(12, 2)),
        sa.column("statut_rapprochement", sa.String(30)),
        sa.column("score_rapprochement", sa.Numeric(5, 2)),
        sa.column("raison_rapprochement", sa.String(500)),
        sa.column("rapprochement_confirme_par", postgresql.UUID(as_uuid=True)),
        sa.column("date_rapprochement", sa.DateTime(timezone=True)),
    )
    allocations = sa.table(
        "rapprochements_bancaires_allocations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("cabinet_id", postgresql.UUID(as_uuid=True)),
        sa.column("entreprise_id", postgresql.UUID(as_uuid=True)),
        sa.column("mouvement_bancaire_id", postgresql.UUID(as_uuid=True)),
        sa.column("ecriture_id", postgresql.UUID(as_uuid=True)),
        sa.column("montant_affecte", sa.Numeric(14, 2)),
        sa.column("statut", sa.String(30)),
        sa.column("score", sa.Numeric(5, 2)),
        sa.column("raison", sa.String(500)),
        sa.column("confirme_par", postgresql.UUID(as_uuid=True)),
        sa.column("date_confirmation", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(
        sa.select(
            mouvements.c.id,
            mouvements.c.cabinet_id,
            mouvements.c.entreprise_id,
            mouvements.c.ecriture_rapprochee_id,
            mouvements.c.montant,
            mouvements.c.statut_rapprochement,
            mouvements.c.score_rapprochement,
            mouvements.c.raison_rapprochement,
            mouvements.c.rapprochement_confirme_par,
            mouvements.c.date_rapprochement,
        ).where(
            mouvements.c.ecriture_rapprochee_id.is_not(None),
            mouvements.c.statut_rapprochement.in_(["automatique", "confirme"]),
        )
    ).all()
    for row in rows:
        exists = bind.execute(
            sa.select(allocations.c.id).where(
                allocations.c.mouvement_bancaire_id == row.id,
                allocations.c.ecriture_id == row.ecriture_rapprochee_id,
            )
        ).first()
        if exists:
            continue
        bind.execute(
            allocations.insert().values(
                id=uuid.uuid4(),
                cabinet_id=row.cabinet_id,
                entreprise_id=row.entreprise_id,
                mouvement_bancaire_id=row.id,
                ecriture_id=row.ecriture_rapprochee_id,
                montant_affecte=row.montant,
                statut=("confirme" if row.statut_rapprochement == "confirme" else "automatique"),
                score=row.score_rapprochement,
                raison=row.raison_rapprochement,
                confirme_par=row.rapprochement_confirme_par,
                date_confirmation=row.date_rapprochement,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "mouvements_bancaires" in tables:
        cols = _columns("mouvements_bancaires")
        with op.batch_alter_table("mouvements_bancaires") as batch:
            if "mode_rapprochement" in cols:
                batch.drop_column("mode_rapprochement")
            if "mouvement_lie_id" in cols:
                try:
                    batch.drop_constraint("fk_mouvement_bancaire_mouvement_lie", type_="foreignkey")
                except Exception:
                    pass
                batch.drop_column("mouvement_lie_id")
            if "compte_contrepartie" in cols:
                batch.drop_column("compte_contrepartie")
            if "nature_operation" in cols:
                batch.drop_column("nature_operation")
            if "compte_bancaire_entreprise_id" in cols:
                try:
                    batch.drop_constraint("fk_mouvement_compte_bancaire_entreprise", type_="foreignkey")
                except Exception:
                    pass
                batch.drop_column("compte_bancaire_entreprise_id")

    tables = set(sa.inspect(bind).get_table_names())
    if "rapprochements_bancaires_allocations" in tables:
        op.drop_table("rapprochements_bancaires_allocations")
    if "comptes_bancaires_entreprise" in tables:
        op.drop_table("comptes_bancaires_entreprise")
