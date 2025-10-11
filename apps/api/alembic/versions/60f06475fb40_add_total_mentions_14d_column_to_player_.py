"""Add total_mentions_14d column to player_hype

Revision ID: 60f06475fb40
Revises: 8bad6ca0a8ad
Create Date: 2025-10-10 20:54:06.965253

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60f06475fb40'
down_revision = '8bad6ca0a8ad'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add total_mentions_14d column to player_hype table
    op.add_column('player_hype', sa.Column('total_mentions_14d', sa.Integer(), nullable=True))

    # Set default value for existing rows
    op.execute('UPDATE player_hype SET total_mentions_14d = 0 WHERE total_mentions_14d IS NULL')


def downgrade() -> None:
    # Remove total_mentions_14d column
    op.drop_column('player_hype', 'total_mentions_14d')