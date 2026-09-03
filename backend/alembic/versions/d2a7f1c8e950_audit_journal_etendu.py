"""Étend le journal d'audit existant sans perdre les anciennes lignes.

Revision ID: d2a7f1c8e950
Revises: c1f6a9b4d803
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d2a7f1c8e950"
down_revision: Union[str, Sequence[str], None] = "c1f6a9b4d803"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("entreprise_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("audit_logs", sa.Column("module", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_type", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("audit_logs", sa.Column("description", sa.String(1000), nullable=True))
    op.add_column("audit_logs", sa.Column("status", sa.String(20), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_type", sa.String(30), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_name", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_email", sa.String(255), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_role", sa.String(50), nullable=True))
    op.add_column("audit_logs", sa.Column("event_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_logs", sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("audit_logs", sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("audit_logs", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("audit_logs", sa.Column("item_count", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(500), nullable=True))
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(128), nullable=True))

    op.create_foreign_key(
        "fk_audit_logs_entreprise", "audit_logs", "entreprises",
        ["entreprise_id"], ["id"], ondelete="SET NULL",
    )
    op.drop_constraint("audit_logs_user_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_audit_logs_user", "audit_logs", "users", ["user_id"], ["id"],
        ondelete="SET NULL",
    )

    op.execute(sa.text("""
        UPDATE audit_logs AS a
        SET module = CASE
                WHEN action LIKE 'user.%' THEN 'utilisateurs'
                WHEN action LIKE 'document.%' THEN 'documents'
                WHEN action LIKE 'accounting_entry.%' THEN 'comptabilite'
                ELSE 'systeme'
            END,
            resource_type = COALESCE(details->>'resource_type', 'systeme'),
            resource_id = CASE
                WHEN COALESCE(details->>'resource_id', '') ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                THEN (details->>'resource_id')::uuid ELSE NULL END,
            old_values = details->'avant',
            new_values = details->'apres',
            status = 'success',
            actor_type = CASE WHEN user_id IS NULL THEN 'system' ELSE 'user' END,
            event_at = created_at
    """))
    op.execute(sa.text("""
        UPDATE audit_logs AS a
        SET actor_name = CONCAT_WS(' ', u.prenom, u.nom),
            actor_email = u.email,
            actor_role = u.role::text
        FROM users AS u
        WHERE a.user_id = u.id
    """))

    op.alter_column("audit_logs", "module", nullable=False, server_default="systeme")
    op.alter_column("audit_logs", "status", nullable=False, server_default="success")
    op.alter_column("audit_logs", "actor_type", nullable=False, server_default="user")
    op.alter_column("audit_logs", "event_at", nullable=False, server_default=sa.text("now()"))

    op.create_index("ix_audit_logs_entreprise_id", "audit_logs", ["entreprise_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_module", "audit_logs", ["module"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_status", "audit_logs", ["status"])
    op.create_index("ix_audit_logs_actor_role", "audit_logs", ["actor_role"])
    op.create_index("ix_audit_logs_event_at", "audit_logs", ["event_at"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])
    op.create_index("ix_audit_logs_cabinet_created", "audit_logs", ["cabinet_id", "event_at"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    for name in (
        "ix_audit_logs_resource", "ix_audit_logs_cabinet_created",
        "ix_audit_logs_correlation_id", "ix_audit_logs_event_at",
        "ix_audit_logs_actor_role", "ix_audit_logs_status",
        "ix_audit_logs_resource_type", "ix_audit_logs_module",
        "ix_audit_logs_user_id", "ix_audit_logs_entreprise_id",
    ):
        op.drop_index(name, table_name="audit_logs")

    op.drop_constraint("fk_audit_logs_user", "audit_logs", type_="foreignkey")
    op.create_foreign_key("audit_logs_user_id_fkey", "audit_logs", "users", ["user_id"], ["id"])
    op.drop_constraint("fk_audit_logs_entreprise", "audit_logs", type_="foreignkey")
    for column in (
        "correlation_id", "user_agent", "item_count", "resource_ids", "metadata",
        "new_values", "old_values", "event_at", "actor_role", "actor_email",
        "actor_name", "actor_type", "status", "description", "resource_id",
        "resource_type", "module", "entreprise_id",
    ):
        op.drop_column("audit_logs", column)
