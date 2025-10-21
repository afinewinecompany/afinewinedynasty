"""Add materialized views for pitch-level percentile rankings

Revision ID: 018
Revises: 017
Create Date: 2025-10-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018'
down_revision = 'c67ca5c732c0'  # Updated to merge from latest head
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create materialized views for hitter and pitcher percentiles by level."""

    # ============================================================================
    # HITTER PERCENTILES BY LEVEL
    # ============================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hitter_percentiles_by_level AS
        WITH recent_stats AS (
            SELECT
                mlb_batter_id,
                level,
                season,

                -- Exit Velocity (90th percentile)
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                    FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                -- Hard Hit Rate
                COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                -- Contact Rate
                COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                -- Whiff Rate
                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                -- Chase Rate
                COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                -- Sample size
                COUNT(*) as pitches_seen,
                COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play

            FROM milb_batter_pitches
            WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'
            GROUP BY mlb_batter_id, level, season
            HAVING COUNT(*) >= 50  -- Minimum 50 pitches
        ),
        level_percentiles AS (
            SELECT
                level,
                season,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY exit_velo_90th) as exit_velo_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY hard_hit_rate) as hard_hit_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY contact_rate) as contact_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY whiff_rate) as whiff_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY chase_rate) as chase_percentiles,
                COUNT(*) as cohort_size
            FROM recent_stats
            GROUP BY level, season
        )
        SELECT * FROM level_percentiles;
    """)

    # Create index on materialized view
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_hitter_perc_level_season
        ON mv_hitter_percentiles_by_level(level, season);
    """)

    # ============================================================================
    # PITCHER PERCENTILES BY LEVEL
    # ============================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_pitcher_percentiles_by_level AS
        WITH recent_stats AS (
            SELECT
                mlb_pitcher_id,
                level,
                season,

                -- Whiff Rate
                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                -- Zone Rate
                COUNT(*) FILTER (WHERE zone BETWEEN 1 AND 9) * 100.0 /
                    NULLIF(COUNT(*), 0) as zone_rate,

                -- Avg FB Velocity
                AVG(start_speed) FILTER (WHERE pitch_type IN ('FF', 'FA', 'SI')
                    AND start_speed IS NOT NULL) as avg_fb_velo,

                -- Hard Contact Rate
                COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_contact_rate,

                -- Chase Rate
                COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                -- Sample size
                COUNT(*) as pitches_thrown,
                COUNT(*) FILTER (WHERE swing = TRUE) as swings_induced,
                COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play_allowed

            FROM milb_pitcher_pitches
            WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'
            GROUP BY mlb_pitcher_id, level, season
            HAVING COUNT(*) >= 100  -- Minimum 100 pitches
        ),
        level_percentiles AS (
            SELECT
                level,
                season,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY whiff_rate) as whiff_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY zone_rate) as zone_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY avg_fb_velo) as velo_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY hard_contact_rate) as hard_contact_percentiles,
                PERCENTILE_CONT(ARRAY[0.10, 0.25, 0.50, 0.75, 0.90])
                    WITHIN GROUP (ORDER BY chase_rate) as chase_percentiles,
                COUNT(*) as cohort_size
            FROM recent_stats
            GROUP BY level, season
        )
        SELECT * FROM level_percentiles;
    """)

    # Create index on materialized view
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_perc_level_season
        ON mv_pitcher_percentiles_by_level(level, season);
    """)

    # ============================================================================
    # VERIFY REQUIRED INDEXES ON SOURCE TABLES
    # ============================================================================

    # These should already exist from previous migrations, but verify:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_batter_pitches_batter_date
        ON milb_batter_pitches(mlb_batter_id, game_date DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_batter_pitches_level_season
        ON milb_batter_pitches(level, season);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher_date
        ON milb_pitcher_pitches(mlb_pitcher_id, game_date DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_level_season
        ON milb_pitcher_pitches(level, season);
    """)

    print("[SUCCESS] Materialized views created successfully")
    print("[INFO] Run initial refresh with: REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;")
    print("[INFO] Run initial refresh with: REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;")


def downgrade() -> None:
    """Remove materialized views."""

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pitcher_percentiles_by_level;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_hitter_percentiles_by_level;")

    print("[SUCCESS] Materialized views dropped successfully")
