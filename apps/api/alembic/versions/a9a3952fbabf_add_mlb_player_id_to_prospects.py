"""add_mlb_player_id_to_prospects

Revision ID: a9a3952fbabf
Revises: 33237cb5bb9b
Create Date: 2025-10-13 09:20:32.185864

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9a3952fbabf'
down_revision = '33237cb5bb9b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add mlb_player_id column to prospects table
    # This will store the actual MLB Stats API player ID
    op.add_column('prospects', sa.Column('mlb_player_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_prospects_mlb_player_id'), 'prospects', ['mlb_player_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prospects_mlb_player_id'), table_name='prospects')
    op.drop_column('prospects', 'mlb_player_id')