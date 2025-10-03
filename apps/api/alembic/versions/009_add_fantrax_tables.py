"""add fantrax tables

Revision ID: 009
Revises: 008
Create Date: 2025-01-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add Fantrax integration tables for league, roster, and sync tracking
    """
    # Add fantrax_connected_at column to users table
    op.add_column('users', sa.Column('fantrax_connected_at', sa.DateTime(), nullable=True))

    # Create fantrax_leagues table
    op.create_table(
        'fantrax_leagues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.String(length=100), nullable=False),
        sa.Column('league_name', sa.String(length=200), nullable=False),
        sa.Column('league_type', sa.String(length=50), nullable=False),
        sa.Column('scoring_system', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('roster_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_sync', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("league_type IN ('dynasty', 'keeper', 'redraft')", name='valid_league_type'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fantrax_leagues_id'), 'fantrax_leagues', ['id'], unique=False)
    op.create_index(op.f('ix_fantrax_leagues_league_id'), 'fantrax_leagues', ['league_id'], unique=False)
    op.create_index('ix_fantrax_leagues_user_league', 'fantrax_leagues', ['user_id', 'league_id'], unique=True)

    # Create fantrax_rosters table
    op.create_table(
        'fantrax_rosters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.String(length=100), nullable=False),
        sa.Column('player_name', sa.String(length=200), nullable=False),
        sa.Column('positions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('contract_years', sa.Integer(), nullable=True),
        sa.Column('contract_value', sa.Float(), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('team', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('minor_league_eligible', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('active', 'injured', 'minors', 'suspended', 'il')", name='valid_player_status'),
        sa.CheckConstraint('age > 0 AND age < 60', name='valid_player_age'),
        sa.CheckConstraint('contract_years >= 0', name='valid_contract_years'),
        sa.ForeignKeyConstraint(['league_id'], ['fantrax_leagues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fantrax_rosters_id'), 'fantrax_rosters', ['id'], unique=False)
    op.create_index('ix_fantrax_rosters_league_player', 'fantrax_rosters', ['league_id', 'player_id'], unique=True)
    # Add GIN index for JSONB array position searches
    op.execute('CREATE INDEX ix_fantrax_rosters_positions_gin ON fantrax_rosters USING gin (positions jsonb_path_ops)')

    # Create fantrax_sync_history table
    op.create_table(
        'fantrax_sync_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('league_id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('players_synced', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sync_duration_ms', sa.Integer(), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("sync_type IN ('roster', 'settings', 'transactions', 'full')", name='valid_sync_type'),
        sa.CheckConstraint('players_synced >= 0', name='valid_players_synced'),
        sa.ForeignKeyConstraint(['league_id'], ['fantrax_leagues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fantrax_sync_history_id'), 'fantrax_sync_history', ['id'], unique=False)
    op.create_index(op.f('ix_fantrax_sync_history_synced_at'), 'fantrax_sync_history', ['synced_at'], unique=False)


def downgrade() -> None:
    """
    Remove Fantrax integration tables
    """
    # Drop tables in reverse order due to foreign key constraints
    op.drop_index(op.f('ix_fantrax_sync_history_synced_at'), table_name='fantrax_sync_history')
    op.drop_index(op.f('ix_fantrax_sync_history_id'), table_name='fantrax_sync_history')
    op.drop_table('fantrax_sync_history')

    op.drop_index('ix_fantrax_rosters_positions_gin', table_name='fantrax_rosters')
    op.drop_index('ix_fantrax_rosters_league_player', table_name='fantrax_rosters')
    op.drop_index(op.f('ix_fantrax_rosters_id'), table_name='fantrax_rosters')
    op.drop_table('fantrax_rosters')

    op.drop_index('ix_fantrax_leagues_user_league', table_name='fantrax_leagues')
    op.drop_index(op.f('ix_fantrax_leagues_league_id'), table_name='fantrax_leagues')
    op.drop_index(op.f('ix_fantrax_leagues_id'), table_name='fantrax_leagues')
    op.drop_table('fantrax_leagues')

    # Remove fantrax_connected_at column from users table
    op.drop_column('users', 'fantrax_connected_at')
