"""ajout saisie_topaze sur ecritures_comptables

Revision ID: e8fd7f46f06e
Revises: 18e58386fcfa
Create Date: 2026-07-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8fd7f46f06e'
down_revision = '18e58386fcfa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CORRECTIF : server_default='false' est indispensable ici -- la
    # table contient déjà des lignes, donc NOT NULL sans valeur par
    # défaut pour les lignes existantes fait échouer l'ALTER TABLE
    # (NotNullViolation). Le server_default remplit automatiquement
    # les lignes existantes à la création de la colonne.
    op.add_column(
        'ecritures_comptables',
        sa.Column('saisie_topaze', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    # On retire le server_default juste après : on voulait seulement
    # qu'il serve UNE FOIS pour remplir les lignes existantes. Sans ce
    # retrait, le modèle Python (qui gère déjà default=False côté
    # SQLAlchemy) et la base auraient deux sources de vérité pour la
    # valeur par défaut, ce qui n'est pas nécessaire ici.
    op.alter_column('ecritures_comptables', 'saisie_topaze', server_default=None)


def downgrade() -> None:
    op.drop_column('ecritures_comptables', 'saisie_topaze')