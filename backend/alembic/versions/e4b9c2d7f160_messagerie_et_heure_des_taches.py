"""Messagerie interne et heure d'échéance des tâches.

Revision ID: e4b9c2d7f160
Revises: d2a7f1c8e950
Create Date: 2026-08-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e4b9c2d7f160"
down_revision: Union[str, Sequence[str], None] = "d2a7f1c8e950"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("taches", sa.Column("heure_echeance", sa.Time(), nullable=True))
    op.create_table(
        "cabinet_messages",
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=30), server_default="chat", nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cabinet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("message_type IN ('chat', 'access_request')", name="ck_cabinet_messages_type"),
        sa.CheckConstraint("length(trim(contenu)) > 0", name="ck_cabinet_messages_contenu"),
        sa.ForeignKeyConstraint(["cabinet_id"], ["cabinets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["taches.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_cabinet_messages_task_id"),
    )
    op.create_index("ix_cabinet_messages_cabinet_id", "cabinet_messages", ["cabinet_id"])
    op.create_index("ix_cabinet_messages_sender_id", "cabinet_messages", ["sender_id"])
    op.create_index("ix_cabinet_messages_recipient_id", "cabinet_messages", ["recipient_id"])
    op.create_index("ix_cabinet_messages_read_at", "cabinet_messages", ["read_at"])
    op.create_index(
        "ix_cabinet_messages_recipient_unread",
        "cabinet_messages",
        ["cabinet_id", "recipient_id", "read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cabinet_messages_recipient_unread", table_name="cabinet_messages")
    op.drop_index("ix_cabinet_messages_read_at", table_name="cabinet_messages")
    op.drop_index("ix_cabinet_messages_recipient_id", table_name="cabinet_messages")
    op.drop_index("ix_cabinet_messages_sender_id", table_name="cabinet_messages")
    op.drop_index("ix_cabinet_messages_cabinet_id", table_name="cabinet_messages")
    op.drop_table("cabinet_messages")
    op.drop_column("taches", "heure_echeance")
