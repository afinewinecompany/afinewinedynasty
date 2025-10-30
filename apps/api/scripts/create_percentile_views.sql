-- Create materialized views for pitch data percentiles
-- These views calculate percentiles for each level to compare players to their peers

-- Drop existing views if they exist
DROP MATERIALIZED VIEW IF EXISTS mv_hitter_percentiles_by_level CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_pitcher_percentiles_by_level CASCADE;

-- Create hitter percentiles view
CREATE MATERIALIZED VIEW mv_hitter_percentiles_by_level AS
WITH hitter_metrics AS (
    SELECT
        mlb_batter_id,
        level,
        season,
        COUNT(*) as pitches_seen,

        -- Contact Rate
        COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

        -- Whiff Rate
        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

        -- Chase Rate (swing at balls)
        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

        -- Exit Velocity (90th percentile) - will be NULL if no data
        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
            FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

        -- Hard Hit Rate
        COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate

    FROM milb_batter_pitches
    WHERE season >= 2025
        AND level IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Complex')
    GROUP BY mlb_batter_id, level, season
    HAVING COUNT(*) >= 50  -- Minimum sample size
)
SELECT
    level,
    season,
    COUNT(*) as num_hitters,

    -- Exit Velocity percentiles (array of p10, p25, p50, p75, p90)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY exit_velo_90th),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY exit_velo_90th),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY exit_velo_90th),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY exit_velo_90th),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY exit_velo_90th)
    ] as exit_velo_percentiles,

    -- Hard Hit Rate percentiles
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY hard_hit_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY hard_hit_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY hard_hit_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY hard_hit_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY hard_hit_rate)
    ] as hard_hit_percentiles,

    -- Contact Rate percentiles
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY contact_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY contact_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY contact_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY contact_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY contact_rate)
    ] as contact_percentiles,

    -- Whiff Rate percentiles (lower is better for hitters)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY whiff_rate)
    ] as whiff_percentiles,

    -- Chase Rate percentiles (lower is better for hitters)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY chase_rate)
    ] as chase_percentiles

FROM hitter_metrics
GROUP BY level, season;

-- Create pitcher percentiles view
CREATE MATERIALIZED VIEW mv_pitcher_percentiles_by_level AS
WITH pitcher_metrics AS (
    SELECT
        mlb_pitcher_id,
        level,
        season,
        COUNT(*) as pitches_thrown,

        -- Whiff Rate (swing and miss)
        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

        -- Zone Rate
        COUNT(*) FILTER (WHERE zone <= 9) * 100.0 /
            NULLIF(COUNT(*), 0) as zone_rate,

        -- Average Fastball Velocity
        AVG(start_speed) FILTER (WHERE pitch_type IN ('FF', 'FA', 'FT', 'FC', 'FS', 'SI'))
            as avg_fb_velo,

        -- Hard Contact Rate Against (lower is better)
        COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_contact_rate,

        -- Chase Rate (getting swings outside zone)
        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate

    FROM milb_pitcher_pitches
    WHERE season >= 2025
        AND level IN ('AAA', 'AA', 'A+', 'A', 'Rookie', 'Complex')
    GROUP BY mlb_pitcher_id, level, season
    HAVING COUNT(*) >= 100  -- Minimum sample size for pitchers
)
SELECT
    level,
    season,
    COUNT(*) as num_pitchers,

    -- Whiff Rate percentiles (higher is better for pitchers)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY whiff_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY whiff_rate)
    ] as whiff_percentiles,

    -- Zone Rate percentiles
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY zone_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY zone_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY zone_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY zone_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY zone_rate)
    ] as zone_percentiles,

    -- Velocity percentiles
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY avg_fb_velo),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY avg_fb_velo),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avg_fb_velo),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY avg_fb_velo),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY avg_fb_velo)
    ] as velo_percentiles,

    -- Hard Contact percentiles (lower is better)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY hard_contact_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY hard_contact_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY hard_contact_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY hard_contact_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY hard_contact_rate)
    ] as hard_contact_percentiles,

    -- Chase Rate percentiles (higher is better for pitchers)
    ARRAY[
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY chase_rate),
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY chase_rate)
    ] as chase_percentiles

FROM pitcher_metrics
GROUP BY level, season;

-- Create indexes for fast lookups
CREATE UNIQUE INDEX idx_hitter_percentiles ON mv_hitter_percentiles_by_level (level, season);
CREATE UNIQUE INDEX idx_pitcher_percentiles ON mv_pitcher_percentiles_by_level (level, season);

-- Add comments
COMMENT ON MATERIALIZED VIEW mv_hitter_percentiles_by_level IS
'Percentile distributions for hitter pitch metrics by level and season. Used for ranking calculations.';

COMMENT ON MATERIALIZED VIEW mv_pitcher_percentiles_by_level IS
'Percentile distributions for pitcher pitch metrics by level and season. Used for ranking calculations.';

-- Refresh the views with current data
REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;
REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;

-- Check the data
SELECT level, season, num_hitters,
       contact_percentiles[3] as median_contact_rate,
       whiff_percentiles[3] as median_whiff_rate,
       chase_percentiles[3] as median_chase_rate
FROM mv_hitter_percentiles_by_level
ORDER BY level, season;