"""Add user lineups and lineup prospects tables

Revision ID: 016
Revises: 015
Create Date: 2025-10-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_lineups table
    op.create_table('user_lineups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('lineup_type', sa.String(length=20), nullable=False, server_default='custom'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("lineup_type IN ('custom', 'fantrax_sync', 'watchlist')", name='valid_lineup_type')
    )
    op.create_index(op.f('ix_user_lineups_id'), 'user_lineups', ['id'], unique=False)
    op.create_index(op.f('ix_user_lineups_user_id'), 'user_lineups', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_lineups_type'), 'user_lineups', ['lineup_type'], unique=False)

    # Create lineup_prospects junction table
    op.create_table('lineup_prospects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lineup_id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.String(length=10), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['lineup_id'], ['user_lineups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('lineup_id', 'prospect_id', name='uq_lineup_prospect')
    )
    op.create_index(op.f('ix_lineup_prospects_id'), 'lineup_prospects', ['id'], unique=False)
    op.create_index(op.f('ix_lineup_prospects_lineup_id'), 'lineup_prospects', ['lineup_id'], unique=False)
    op.create_index(op.f('ix_lineup_prospects_prospect_id'), 'lineup_prospects', ['prospect_id'], unique=False)


def downgrade() -> None:
    # Drop lineup_prospects table
    op.drop_index(op.f('ix_lineup_prospects_prospect_id'), table_name='lineup_prospects')
    op.drop_index(op.f('ix_lineup_prospects_lineup_id'), table_name='lineup_prospects')
    op.drop_index(op.f('ix_lineup_prospects_id'), table_name='lineup_prospects')
    op.drop_table('lineup_prospects')

    # Drop user_lineups table
    op.drop_index(op.f('ix_user_lineups_type'), table_name='user_lineups')
    op.drop_index(op.f('ix_user_lineups_user_id'), table_name='user_lineups')
    op.drop_index(op.f('ix_user_lineups_id'), table_name='user_lineups')
    op.drop_table('user_lineups')
