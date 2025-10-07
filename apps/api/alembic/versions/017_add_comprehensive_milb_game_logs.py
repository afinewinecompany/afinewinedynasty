"""add comprehensive milb game logs table with all MLB API stats

Revision ID: 017
Revises: 016
Create Date: 2025-10-06

Stores ALL available stats from MLB Stats API game logs:
- 36 hitting stats per game
- 63 pitching stats per game
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    """Create comprehensive milb_game_logs table with all MLB Stats API fields."""

    op.create_table(
        'milb_game_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prospect_id', sa.Integer(), nullable=False),
        sa.Column('mlb_player_id', sa.Integer(), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('game_pk', sa.BigInteger(), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('game_type', sa.String(length=1), nullable=False, comment='R=Regular, S=Spring, P=Playoffs'),

        # Game context
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('opponent_id', sa.Integer(), nullable=True),
        sa.Column('is_home', sa.Boolean(), nullable=True),

        # === HITTING STATS (36 fields from MLB API) ===
        # Basic counting stats
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('at_bats', sa.Integer(), nullable=True),
        sa.Column('plate_appearances', sa.Integer(), nullable=True),
        sa.Column('runs', sa.Integer(), nullable=True),
        sa.Column('hits', sa.Integer(), nullable=True),
        sa.Column('doubles', sa.Integer(), nullable=True),
        sa.Column('triples', sa.Integer(), nullable=True),
        sa.Column('home_runs', sa.Integer(), nullable=True),
        sa.Column('rbi', sa.Integer(), nullable=True),
        sa.Column('total_bases', sa.Integer(), nullable=True),

        # Plate discipline
        sa.Column('walks', sa.Integer(), nullable=True),
        sa.Column('intentional_walks', sa.Integer(), nullable=True),
        sa.Column('strikeouts', sa.Integer(), nullable=True),
        sa.Column('hit_by_pitch', sa.Integer(), nullable=True),

        # Baserunning
        sa.Column('stolen_bases', sa.Integer(), nullable=True),
        sa.Column('caught_stealing', sa.Integer(), nullable=True),

        # Outs
        sa.Column('fly_outs', sa.Integer(), nullable=True),
        sa.Column('ground_outs', sa.Integer(), nullable=True),
        sa.Column('air_outs', sa.Integer(), nullable=True),
        sa.Column('ground_into_double_play', sa.Integer(), nullable=True),
        sa.Column('ground_into_triple_play', sa.Integer(), nullable=True),

        # Other
        sa.Column('sac_bunts', sa.Integer(), nullable=True),
        sa.Column('sac_flies', sa.Integer(), nullable=True),
        sa.Column('left_on_base', sa.Integer(), nullable=True),
        sa.Column('number_of_pitches', sa.Integer(), nullable=True),
        sa.Column('catchers_interference', sa.Integer(), nullable=True),

        # Rate stats
        sa.Column('batting_avg', sa.Float(), nullable=True),
        sa.Column('obp', sa.Float(), nullable=True),
        sa.Column('slg', sa.Float(), nullable=True),
        sa.Column('ops', sa.Float(), nullable=True),
        sa.Column('babip', sa.Float(), nullable=True),
        sa.Column('stolen_base_percentage', sa.Float(), nullable=True),
        sa.Column('ground_outs_to_airouts', sa.Float(), nullable=True),
        sa.Column('at_bats_per_home_run', sa.Float(), nullable=True),

        # === PITCHING STATS (63 fields from MLB API) ===
        # Basic pitching
        sa.Column('games_started', sa.Integer(), nullable=True),
        sa.Column('games_pitched', sa.Integer(), nullable=True),
        sa.Column('complete_games', sa.Integer(), nullable=True),
        sa.Column('shutouts', sa.Integer(), nullable=True),
        sa.Column('games_finished', sa.Integer(), nullable=True),
        sa.Column('wins', sa.Integer(), nullable=True),
        sa.Column('losses', sa.Integer(), nullable=True),
        sa.Column('saves', sa.Integer(), nullable=True),
        sa.Column('save_opportunities', sa.Integer(), nullable=True),
        sa.Column('holds', sa.Integer(), nullable=True),
        sa.Column('blown_saves', sa.Integer(), nullable=True),

        # Innings and outs
        sa.Column('innings_pitched', sa.Float(), nullable=True),
        sa.Column('outs', sa.Integer(), nullable=True),
        sa.Column('batters_faced', sa.Integer(), nullable=True),

        # Pitches
        sa.Column('number_of_pitches_pitched', sa.Integer(), nullable=True),
        sa.Column('strikes', sa.Integer(), nullable=True),

        # Results allowed
        sa.Column('hits_allowed', sa.Integer(), nullable=True),
        sa.Column('runs_allowed', sa.Integer(), nullable=True),
        sa.Column('earned_runs', sa.Integer(), nullable=True),
        sa.Column('home_runs_allowed', sa.Integer(), nullable=True),
        sa.Column('walks_allowed', sa.Integer(), nullable=True),
        sa.Column('intentional_walks_allowed', sa.Integer(), nullable=True),
        sa.Column('strikeouts_pitched', sa.Integer(), nullable=True),
        sa.Column('hit_batsmen', sa.Integer(), nullable=True),

        # Baserunning allowed
        sa.Column('stolen_bases_allowed', sa.Integer(), nullable=True),
        sa.Column('caught_stealing_allowed', sa.Integer(), nullable=True),

        # Other pitching events
        sa.Column('balks', sa.Integer(), nullable=True),
        sa.Column('wild_pitches', sa.Integer(), nullable=True),
        sa.Column('pickoffs', sa.Integer(), nullable=True),
        sa.Column('inherited_runners', sa.Integer(), nullable=True),
        sa.Column('inherited_runners_scored', sa.Integer(), nullable=True),

        # Outs recorded
        sa.Column('fly_outs_pitched', sa.Integer(), nullable=True),
        sa.Column('ground_outs_pitched', sa.Integer(), nullable=True),
        sa.Column('air_outs_pitched', sa.Integer(), nullable=True),
        sa.Column('ground_into_double_play_pitched', sa.Integer(), nullable=True),

        # Other
        sa.Column('total_bases_allowed', sa.Integer(), nullable=True),
        sa.Column('sac_bunts_allowed', sa.Integer(), nullable=True),
        sa.Column('sac_flies_allowed', sa.Integer(), nullable=True),
        sa.Column('catchers_interference_pitched', sa.Integer(), nullable=True),

        # Pitching rate stats
        sa.Column('era', sa.Float(), nullable=True),
        sa.Column('whip', sa.Float(), nullable=True),
        sa.Column('avg_against', sa.Float(), nullable=True),
        sa.Column('obp_against', sa.Float(), nullable=True),
        sa.Column('slg_against', sa.Float(), nullable=True),
        sa.Column('ops_against', sa.Float(), nullable=True),
        sa.Column('win_percentage', sa.Float(), nullable=True),
        sa.Column('strike_percentage', sa.Float(), nullable=True),
        sa.Column('pitches_per_inning', sa.Float(), nullable=True),
        sa.Column('strikeout_walk_ratio', sa.Float(), nullable=True),
        sa.Column('strikeouts_per_9inn', sa.Float(), nullable=True),
        sa.Column('walks_per_9inn', sa.Float(), nullable=True),
        sa.Column('hits_per_9inn', sa.Float(), nullable=True),
        sa.Column('runs_scored_per_9', sa.Float(), nullable=True),
        sa.Column('home_runs_per_9', sa.Float(), nullable=True),
        sa.Column('stolen_base_percentage_against', sa.Float(), nullable=True),
        sa.Column('ground_outs_to_airouts_pitched', sa.Float(), nullable=True),

        # Metadata
        sa.Column('data_source', sa.String(length=50), nullable=False, default='mlb_stats_api'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['prospect_id'], ['prospects.id'], ondelete='CASCADE'),
    )

    # Indexes for efficient querying
    op.create_index('idx_milb_game_logs_prospect', 'milb_game_logs', ['prospect_id'])
    op.create_index('idx_milb_game_logs_mlb_player', 'milb_game_logs', ['mlb_player_id'])
    op.create_index('idx_milb_game_logs_season', 'milb_game_logs', ['season'])
    op.create_index('idx_milb_game_logs_game_date', 'milb_game_logs', ['game_date'])
    op.create_index('idx_milb_game_logs_game_pk', 'milb_game_logs', ['game_pk'])

    # Unique constraint to prevent duplicate game entries
    op.create_index(
        'idx_milb_game_logs_unique_game',
        'milb_game_logs',
        ['mlb_player_id', 'game_pk', 'season'],
        unique=True
    )


def downgrade():
    """Drop milb_game_logs table."""
    op.drop_index('idx_milb_game_logs_unique_game', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_game_pk', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_game_date', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_season', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_mlb_player', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_prospect', table_name='milb_game_logs')
    op.drop_table('milb_game_logs')
