"""add_missing_milb_columns

Adds comprehensive MLB API stats columns to existing milb_game_logs table.
Existing table only has ~39 columns, this adds 60+ more fields for:
- Advanced hitting stats (total_bases, catchers_interference, etc.)
- Complete pitching stats (63 fields)
- MLB player ID and game PK for tracking

Revision ID: 6f9aa7d4751c
Revises: 017
Create Date: 2025-10-06 12:01:55.141769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f9aa7d4751c'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing comprehensive MLB API stat columns."""

    # Add tracking fields
    op.add_column('milb_game_logs', sa.Column('mlb_player_id', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('game_pk', sa.BigInteger(), nullable=True))

    # Add missing hitting stats
    op.add_column('milb_game_logs', sa.Column('total_bases', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ground_into_triple_play', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('sac_bunts', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('number_of_pitches', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('catchers_interference', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('stolen_base_percentage', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ground_outs_to_airouts', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('at_bats_per_home_run', sa.Float(), nullable=True))

    # Add ALL pitching stats (63 fields)
    op.add_column('milb_game_logs', sa.Column('games_started', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('games_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('complete_games', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('shutouts', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('games_finished', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('wins', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('losses', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('saves', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('save_opportunities', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('holds', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('blown_saves', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('innings_pitched', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('outs', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('batters_faced', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('number_of_pitches_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('strikes', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('hits_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('runs_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('earned_runs', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('home_runs_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('walks_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('intentional_walks_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('strikeouts_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('hit_batsmen', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('stolen_bases_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('caught_stealing_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('balks', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('wild_pitches', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('pickoffs', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('inherited_runners', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('inherited_runners_scored', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('fly_outs_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ground_outs_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('air_outs_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ground_into_double_play_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('total_bases_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('sac_bunts_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('sac_flies_allowed', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('catchers_interference_pitched', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('era', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('whip', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('avg_against', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('obp_against', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('slg_against', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ops_against', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('win_percentage', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('strike_percentage', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('pitches_per_inning', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('strikeout_walk_ratio', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('strikeouts_per_9inn', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('walks_per_9inn', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('hits_per_9inn', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('runs_scored_per_9', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('home_runs_per_9', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('stolen_base_percentage_against', sa.Float(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('ground_outs_to_airouts_pitched', sa.Float(), nullable=True))

    # Add metadata column
    op.add_column('milb_game_logs', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Add team/opponent IDs (different from existing text columns)
    op.add_column('milb_game_logs', sa.Column('team_id', sa.Integer(), nullable=True))
    op.add_column('milb_game_logs', sa.Column('opponent_id', sa.Integer(), nullable=True))

    # Create indexes for new tracking fields
    op.create_index('idx_milb_game_logs_mlb_player', 'milb_game_logs', ['mlb_player_id'], unique=False)
    op.create_index('idx_milb_game_logs_game_pk', 'milb_game_logs', ['game_pk'], unique=False)

    # Create unique constraint to prevent duplicate game entries
    op.create_unique_constraint(
        'uq_milb_game_logs_game_player',
        'milb_game_logs',
        ['game_pk', 'mlb_player_id']
    )


def downgrade() -> None:
    """Remove added columns."""

    # Drop unique constraint and indexes
    op.drop_constraint('uq_milb_game_logs_game_player', 'milb_game_logs', type_='unique')
    op.drop_index('idx_milb_game_logs_game_pk', table_name='milb_game_logs')
    op.drop_index('idx_milb_game_logs_mlb_player', table_name='milb_game_logs')

    # Drop all added columns
    op.drop_column('milb_game_logs', 'opponent_id')
    op.drop_column('milb_game_logs', 'team_id')
    op.drop_column('milb_game_logs', 'updated_at')

    # Drop pitching stats
    op.drop_column('milb_game_logs', 'ground_outs_to_airouts_pitched')
    op.drop_column('milb_game_logs', 'stolen_base_percentage_against')
    op.drop_column('milb_game_logs', 'home_runs_per_9')
    op.drop_column('milb_game_logs', 'runs_scored_per_9')
    op.drop_column('milb_game_logs', 'hits_per_9inn')
    op.drop_column('milb_game_logs', 'walks_per_9inn')
    op.drop_column('milb_game_logs', 'strikeouts_per_9inn')
    op.drop_column('milb_game_logs', 'strikeout_walk_ratio')
    op.drop_column('milb_game_logs', 'pitches_per_inning')
    op.drop_column('milb_game_logs', 'strike_percentage')
    op.drop_column('milb_game_logs', 'win_percentage')
    op.drop_column('milb_game_logs', 'ops_against')
    op.drop_column('milb_game_logs', 'slg_against')
    op.drop_column('milb_game_logs', 'obp_against')
    op.drop_column('milb_game_logs', 'avg_against')
    op.drop_column('milb_game_logs', 'whip')
    op.drop_column('milb_game_logs', 'era')
    op.drop_column('milb_game_logs', 'catchers_interference_pitched')
    op.drop_column('milb_game_logs', 'sac_flies_allowed')
    op.drop_column('milb_game_logs', 'sac_bunts_allowed')
    op.drop_column('milb_game_logs', 'total_bases_allowed')
    op.drop_column('milb_game_logs', 'ground_into_double_play_pitched')
    op.drop_column('milb_game_logs', 'air_outs_pitched')
    op.drop_column('milb_game_logs', 'ground_outs_pitched')
    op.drop_column('milb_game_logs', 'fly_outs_pitched')
    op.drop_column('milb_game_logs', 'inherited_runners_scored')
    op.drop_column('milb_game_logs', 'inherited_runners')
    op.drop_column('milb_game_logs', 'pickoffs')
    op.drop_column('milb_game_logs', 'wild_pitches')
    op.drop_column('milb_game_logs', 'balks')
    op.drop_column('milb_game_logs', 'caught_stealing_allowed')
    op.drop_column('milb_game_logs', 'stolen_bases_allowed')
    op.drop_column('milb_game_logs', 'hit_batsmen')
    op.drop_column('milb_game_logs', 'strikeouts_pitched')
    op.drop_column('milb_game_logs', 'intentional_walks_allowed')
    op.drop_column('milb_game_logs', 'walks_allowed')
    op.drop_column('milb_game_logs', 'home_runs_allowed')
    op.drop_column('milb_game_logs', 'earned_runs')
    op.drop_column('milb_game_logs', 'runs_allowed')
    op.drop_column('milb_game_logs', 'hits_allowed')
    op.drop_column('milb_game_logs', 'strikes')
    op.drop_column('milb_game_logs', 'number_of_pitches_pitched')
    op.drop_column('milb_game_logs', 'batters_faced')
    op.drop_column('milb_game_logs', 'outs')
    op.drop_column('milb_game_logs', 'innings_pitched')
    op.drop_column('milb_game_logs', 'blown_saves')
    op.drop_column('milb_game_logs', 'holds')
    op.drop_column('milb_game_logs', 'save_opportunities')
    op.drop_column('milb_game_logs', 'saves')
    op.drop_column('milb_game_logs', 'losses')
    op.drop_column('milb_game_logs', 'wins')
    op.drop_column('milb_game_logs', 'games_finished')
    op.drop_column('milb_game_logs', 'shutouts')
    op.drop_column('milb_game_logs', 'complete_games')
    op.drop_column('milb_game_logs', 'games_pitched')
    op.drop_column('milb_game_logs', 'games_started')

    # Drop hitting stats
    op.drop_column('milb_game_logs', 'at_bats_per_home_run')
    op.drop_column('milb_game_logs', 'ground_outs_to_airouts')
    op.drop_column('milb_game_logs', 'stolen_base_percentage')
    op.drop_column('milb_game_logs', 'catchers_interference')
    op.drop_column('milb_game_logs', 'number_of_pitches')
    op.drop_column('milb_game_logs', 'sac_bunts')
    op.drop_column('milb_game_logs', 'ground_into_triple_play')
    op.drop_column('milb_game_logs', 'total_bases')

    # Drop tracking fields
    op.drop_column('milb_game_logs', 'game_pk')
    op.drop_column('milb_game_logs', 'mlb_player_id')