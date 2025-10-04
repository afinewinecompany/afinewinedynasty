"""Add prospect_stats hypertable

Revision ID: 003
Revises: 002
Create Date: 2025-09-25 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create prospect_stats table
    op.create_table('prospect_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('date_recorded', sa.Date(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('at_bats', sa.Integer(), nullable=True),
        sa.Column('hits', sa.Integer(), nullable=True),
        sa.Column('home_runs', sa.Integer(), nullable=True),
        sa.Column('rbi', sa.Integer(), nullable=True),
        sa.Column('stolen_bases', sa.Integer(), nullable=True),
        sa.Column('walks', sa.Integer(), nullable=True),
        sa.Column('strikeouts', sa.Integer(), nullable=True),
        sa.Column('batting_avg', sa.Float(), nullable=True),
        sa.Column('on_base_pct', sa.Float(), nullable=True),
        sa.Column('slugging_pct', sa.Float(), nullable=True),
        sa.Column('innings_pitched', sa.Float(), nullable=True),
        sa.Column('earned_runs', sa.Integer(), nullable=True),
        sa.Column('era', sa.Float(), nullable=True),
        sa.Column('whip', sa.Float(), nullable=True),
        sa.Column('strikeouts_per_nine', sa.Float(), nullable=True),
        sa.Column('walks_per_nine', sa.Float(), nullable=True),
        sa.Column('woba', sa.Float(), nullable=True),
        sa.Column('wrc_plus', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("season >= 2020 AND season <= 2035", name='valid_season'),
        sa.CheckConstraint("games_played >= 0", name='valid_games_played'),
        sa.CheckConstraint("at_bats >= 0", name='valid_at_bats'),
        sa.CheckConstraint("hits >= 0", name='valid_hits'),
        sa.CheckConstraint("batting_avg >= 0.0 AND batting_avg <= 1.0", name='valid_batting_avg'),
        sa.CheckConstraint("era >= 0.0", name='valid_era'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prospect_stats_id'), 'prospect_stats', ['id'], unique=False)
    op.create_index(op.f('ix_prospect_stats_date_recorded'), 'prospect_stats', ['date_recorded'], unique=False)

    # Convert to TimescaleDB hypertable with monthly partitioning
    # This requires TimescaleDB extension to be enabled in the database
    # Gracefully skip if TimescaleDB is not available (e.g., in development or Railway)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
            ) THEN
                PERFORM create_hypertable('prospect_stats', 'date_recorded', chunk_time_interval => INTERVAL '1 month');
            ELSE
                RAISE NOTICE 'TimescaleDB extension not found, skipping hypertable creation';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_prospect_stats_date_recorded'), table_name='prospect_stats')
    op.drop_index(op.f('ix_prospect_stats_id'), table_name='prospect_stats')
    op.drop_table('prospect_stats')