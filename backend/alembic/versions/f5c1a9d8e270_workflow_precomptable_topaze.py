"""Workflow pré-comptable Topaze, déclaration TVA et périodes de travail.

Revision ID: f5c1a9d8e270
Revises: e4b9c2d7f160
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f5c1a9d8e270"
down_revision = "e4b9c2d7f160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL exige que les nouvelles valeurs d'enum soient validées avant
    # leur utilisation dans les UPDATE suivants.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE statut_validation_enum ADD VALUE IF NOT EXISTS 'CALCUL_EN_COURS'")
        op.execute("ALTER TYPE statut_validation_enum ADD VALUE IF NOT EXISTS 'PRETE_TOPAZE'")
        op.execute("ALTER TYPE statut_validation_enum ADD VALUE IF NOT EXISTS 'SAISIE_TOPAZE'")

    op.add_column("ecritures_comptables", sa.Column("ready_for_topaze_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ecritures_comptables", sa.Column("topaze_entered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ecritures_comptables", sa.Column("topaze_entered_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("ecritures_comptables", sa.Column("topaze_batch_reference", sa.String(length=100), nullable=True))
    op.create_foreign_key(
        "fk_ecritures_topaze_entered_by_users", "ecritures_comptables", "users",
        ["topaze_entered_by"], ["id"], ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE ecritures_comptables
        SET statut_validation = CASE
            WHEN saisie_topaze IS TRUE THEN 'SAISIE_TOPAZE'::statut_validation_enum
            ELSE 'PRETE_TOPAZE'::statut_validation_enum
        END,
        ready_for_topaze_at = COALESCE(ready_for_topaze_at, updated_at, created_at),
        topaze_entered_at = CASE
            WHEN saisie_topaze IS TRUE THEN COALESCE(topaze_entered_at, updated_at, created_at)
            ELSE topaze_entered_at
        END
        WHERE statut_validation = 'VALIDE'::statut_validation_enum
        """
    )

    op.add_column("tva_configurations_entreprise", sa.Column("jour_limite_declaration", sa.Integer(), nullable=True))
    op.add_column("tva_configurations_entreprise", sa.Column("delai_saisie_topaze_jours", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_tva_configuration_jour_limite", "tva_configurations_entreprise",
        "jour_limite_declaration IS NULL OR (jour_limite_declaration BETWEEN 1 AND 31)",
    )
    op.create_check_constraint(
        "ck_tva_configuration_delai_topaze", "tva_configurations_entreprise",
        "delai_saisie_topaze_jours IS NULL OR delai_saisie_topaze_jours >= 0",
    )

    for column in (
        sa.Column("statut_comptable", sa.String(length=30), nullable=False, server_default="calcul_en_cours"),
        sa.Column("statut_declaration", sa.String(length=30), nullable=False, server_default="a_preparer"),
        sa.Column("date_limite_declaration", sa.Date(), nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declared_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("declaration_date_reelle", sa.Date(), nullable=True),
        sa.Column("declaration_reference", sa.String(length=150), nullable=True),
        sa.Column("declaration_receipt_path", sa.String(length=1000), nullable=True),
        sa.Column("declaration_note", sa.Text(), nullable=True),
    ):
        op.add_column("tva_periodes", column)
    op.create_foreign_key(
        "fk_tva_periodes_declared_by_users", "tva_periodes", "users",
        ["declared_by"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "anomalies_comptables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ecriture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tva_periode_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type_anomalie", sa.String(length=80), nullable=False),
        sa.Column("gravite", sa.String(length=20), nullable=False, server_default="bloquante"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("champ_concerne", sa.String(length=100), nullable=True),
        sa.Column("valeur_detectee", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ecriture_id"], ["ecritures_comptables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tva_periode_id"], ["tva_periodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_anomalies_comptables_cabinet_id", "cabinet_id"),
        ("ix_anomalies_comptables_entreprise_id", "entreprise_id"),
        ("ix_anomalies_comptables_document_id", "document_id"),
        ("ix_anomalies_comptables_ecriture_id", "ecriture_id"),
        ("ix_anomalies_comptables_tva_periode_id", "tva_periode_id"),
    ):
        op.create_index(name, "anomalies_comptables", [column])

    op.create_table(
        "documents_attendus_configuration",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type_document", sa.String(length=80), nullable=False),
        sa.Column("frequence", sa.String(length=30), nullable=False),
        sa.Column("periode_debut", sa.Date(), nullable=False),
        sa.Column("periode_fin", sa.Date(), nullable=False),
        sa.Column("date_limite_reception", sa.Date(), nullable=False),
        sa.Column("nombre_attendu", sa.Integer(), nullable=True),
        sa.Column("responsable_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("complete_manuellement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("complete_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("complete_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsable_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["complete_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cabinet_id", "entreprise_id", "type_document", "periode_debut", "periode_fin", name="uq_document_attendu_tenant_periode"),
        sa.CheckConstraint("nombre_attendu IS NULL OR nombre_attendu >= 0", name="ck_document_attendu_nombre"),
        sa.CheckConstraint("periode_fin >= periode_debut", name="ck_document_attendu_periode"),
    )
    op.create_index("ix_documents_attendus_configuration_cabinet_id", "documents_attendus_configuration", ["cabinet_id"])
    op.create_index("ix_documents_attendus_configuration_entreprise_id", "documents_attendus_configuration", ["entreprise_id"])

    op.create_table(
        "periodes_travail",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exercice", sa.Integer(), nullable=False),
        sa.Column("periode_debut", sa.Date(), nullable=False),
        sa.Column("periode_fin", sa.Date(), nullable=False),
        sa.Column("date_limite_saisie_topaze", sa.Date(), nullable=True),
        sa.Column("verrouillee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entreprise_id"], ["entreprises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reopened_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cabinet_id", "entreprise_id", "periode_debut", "periode_fin", name="uq_periode_travail_tenant"),
        sa.CheckConstraint("periode_fin >= periode_debut", name="ck_periode_travail_dates"),
    )
    op.create_index("ix_periodes_travail_cabinet_id", "periodes_travail", ["cabinet_id"])
    op.create_index("ix_periodes_travail_entreprise_id", "periodes_travail", ["entreprise_id"])
    op.create_index("ix_periodes_travail_exercice", "periodes_travail", ["exercice"])


def downgrade() -> None:
    op.drop_table("periodes_travail")
    op.drop_table("documents_attendus_configuration")
    op.drop_table("anomalies_comptables")
    op.drop_constraint("fk_tva_periodes_declared_by_users", "tva_periodes", type_="foreignkey")
    for name in (
        "declaration_note", "declaration_receipt_path", "declaration_reference",
        "declaration_date_reelle", "declared_by", "declared_at",
        "date_limite_declaration", "statut_declaration", "statut_comptable",
    ):
        op.drop_column("tva_periodes", name)
    op.drop_constraint("ck_tva_configuration_delai_topaze", "tva_configurations_entreprise", type_="check")
    op.drop_constraint("ck_tva_configuration_jour_limite", "tva_configurations_entreprise", type_="check")
    op.drop_column("tva_configurations_entreprise", "delai_saisie_topaze_jours")
    op.drop_column("tva_configurations_entreprise", "jour_limite_declaration")
    op.drop_constraint("fk_ecritures_topaze_entered_by_users", "ecritures_comptables", type_="foreignkey")
    op.drop_column("ecritures_comptables", "topaze_batch_reference")
    op.drop_column("ecritures_comptables", "topaze_entered_by")
    op.drop_column("ecritures_comptables", "topaze_entered_at")
    op.drop_column("ecritures_comptables", "ready_for_topaze_at")
    # Les valeurs ajoutées à un enum PostgreSQL ne sont volontairement pas
    # supprimées : les retirer imposerait de recréer le type et serait risqué.
