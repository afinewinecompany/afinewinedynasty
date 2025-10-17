-- ============================================================================
-- PITCHER PITCH-BY-PITCH DATABASE SCHEMA
-- ============================================================================
-- This table stores detailed pitch-by-pitch data for MiLB pitchers
-- Captures individual pitch metrics from each plate appearance
-- ============================================================================

CREATE TABLE IF NOT EXISTS milb_pitcher_pitches (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Player & Game Identification
    mlb_pitcher_id INTEGER NOT NULL,              -- MLB Stats API pitcher ID
    mlb_batter_id INTEGER NOT NULL,               -- MLB Stats API batter ID
    game_pk BIGINT NOT NULL,                      -- MLB game primary key
    game_date DATE,                               -- Date of game
    season INTEGER,                               -- Season year
    level VARCHAR(20),                            -- MiLB level (AAA, AA, A+, A, Rookie)

    -- Plate Appearance Context
    at_bat_index INTEGER,                         -- Index of at-bat in game
    pitch_number INTEGER,                         -- Pitch number in at-bat (1, 2, 3...)
    inning INTEGER,                               -- Inning number
    half_inning VARCHAR(10),                      -- 'top' or 'bottom'

    -- Pitch Classification
    pitch_type VARCHAR(10),                       -- FF, SL, CH, CU, SI, etc.
    pitch_type_description VARCHAR(50),           -- 4-Seam Fastball, Slider, etc.

    -- Pitch Velocity & Movement
    start_speed FLOAT,                            -- Release velocity (mph)
    end_speed FLOAT,                              -- Velocity at plate (mph)
    pfx_x FLOAT,                                  -- Horizontal movement (inches)
    pfx_z FLOAT,                                  -- Vertical movement (inches)

    -- Release Point
    release_pos_x FLOAT,                          -- Horizontal release position
    release_pos_y FLOAT,                          -- Distance from rubber (feet)
    release_pos_z FLOAT,                          -- Vertical release height
    release_extension FLOAT,                      -- Extension toward plate (feet)

    -- Spin Metrics
    spin_rate FLOAT,                              -- Spin rate (rpm)
    spin_direction FLOAT,                         -- Spin axis (degrees)

    -- Pitch Location
    plate_x FLOAT,                                -- Horizontal location at plate
    plate_z FLOAT,                                -- Vertical location at plate
    zone INTEGER,                                 -- Strike zone (1-9 strike, 11+ ball)

    -- Pitch Result
    pitch_call VARCHAR(50),                       -- Ball, Called Strike, Swinging Strike, Foul, In Play
    pitch_result VARCHAR(50),                     -- Description of pitch outcome
    is_strike BOOLEAN,                            -- Whether pitch was a strike

    -- Counts
    balls INTEGER,                                -- Ball count before pitch
    strikes INTEGER,                              -- Strike count before pitch
    outs INTEGER,                                 -- Outs before pitch

    -- At-Bat Result (for final pitch)
    is_final_pitch BOOLEAN DEFAULT FALSE,         -- Is this the last pitch of PA?
    pa_result VARCHAR(100),                       -- Strikeout, Single, Groundout, etc.
    pa_result_description TEXT,                   -- Full description of PA result

    -- Batted Ball Data (if pitch resulted in contact)
    launch_speed FLOAT,                           -- Exit velocity (mph)
    launch_angle FLOAT,                           -- Launch angle (degrees)
    total_distance FLOAT,                         -- Distance traveled (feet)
    trajectory VARCHAR(20),                       -- Line drive, Ground ball, Fly ball, Popup
    hardness VARCHAR(20),                         -- Hard, Medium, Soft

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint: one pitch per pitcher per game per at-bat per pitch number
    UNIQUE(mlb_pitcher_id, game_pk, at_bat_index, pitch_number)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index on pitcher for quick player lookups
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher
ON milb_pitcher_pitches(mlb_pitcher_id);

-- Index on season for temporal queries
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_season
ON milb_pitcher_pitches(season);

-- Composite index for pitcher + season queries
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher_season
ON milb_pitcher_pitches(mlb_pitcher_id, season);

-- Index on game_pk for game-level queries
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_game
ON milb_pitcher_pitches(game_pk);

-- Index on pitch type for repertoire analysis
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_type
ON milb_pitcher_pitches(pitch_type)
WHERE pitch_type IS NOT NULL;

-- Index on velocity for velocity-based queries
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_velocity
ON milb_pitcher_pitches(start_speed)
WHERE start_speed IS NOT NULL;

-- Index on launch metrics for batted ball analysis
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_launch
ON milb_pitcher_pitches(launch_speed, launch_angle)
WHERE launch_speed IS NOT NULL;

-- ============================================================================
-- SUMMARY/AGGREGATION VIEW (OPTIONAL)
-- ============================================================================
-- This view provides per-pitcher, per-season aggregated stats

CREATE OR REPLACE VIEW pitcher_pbp_summary AS
SELECT
    mlb_pitcher_id,
    season,
    level,
    COUNT(DISTINCT game_pk) as games_pitched,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT at_bat_index || '-' || game_pk) as batters_faced,

    -- Pitch Type Usage
    COUNT(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN 1 END) as fastballs,
    COUNT(CASE WHEN pitch_type IN ('SL', 'SV') THEN 1 END) as sliders,
    COUNT(CASE WHEN pitch_type IN ('CH', 'FS') THEN 1 END) as changeups,
    COUNT(CASE WHEN pitch_type LIKE 'CU%' OR pitch_type = 'KC' THEN 1 END) as curveballs,

    -- Velocity Metrics
    AVG(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN start_speed END) as avg_fb_velo,
    MAX(start_speed) as max_velo,
    AVG(start_speed) as avg_velo,

    -- Spin Metrics
    AVG(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN spin_rate END) as avg_fb_spin,
    AVG(spin_rate) as avg_spin,

    -- Results
    COUNT(CASE WHEN is_strike THEN 1 END) as strikes,
    COUNT(CASE WHEN NOT is_strike THEN 1 END) as balls,
    ROUND(COUNT(CASE WHEN is_strike THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as strike_pct,

    -- Whiff Rate (swinging strikes)
    COUNT(CASE WHEN pitch_call LIKE '%Swinging Strike%' THEN 1 END) as whiffs,
    ROUND(COUNT(CASE WHEN pitch_call LIKE '%Swinging Strike%' THEN 1 END)::NUMERIC /
          NULLIF(COUNT(*), 0) * 100, 1) as whiff_pct,

    -- Batted Ball
    COUNT(CASE WHEN launch_speed IS NOT NULL THEN 1 END) as balls_in_play,
    AVG(launch_speed) as avg_exit_velo,
    AVG(CASE WHEN launch_speed >= 95 THEN 1 ELSE 0 END) as hard_hit_pct,

    -- Outcomes
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Strikeout%' THEN 1 END) as strikeouts,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Walk%' THEN 1 END) as walks,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Home Run%' THEN 1 END) as home_runs_allowed,

    MIN(created_at) as first_collection_date,
    MAX(created_at) as last_collection_date

FROM milb_pitcher_pitches
GROUP BY mlb_pitcher_id, season, level;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE milb_pitcher_pitches IS
'Detailed pitch-by-pitch data for MiLB pitchers from MLB Stats API. Each row represents a single pitch.';

COMMENT ON COLUMN milb_pitcher_pitches.pitch_type IS
'MLB pitch type code: FF=4-seam, SI=sinker, FC=cutter, SL=slider, CU=curve, KC=knuckle curve, CH=change, FS=splitter, etc.';

COMMENT ON COLUMN milb_pitcher_pitches.zone IS
'Strike zone location: 1-9 are in strike zone (3x3 grid), 11+ are out of zone';

COMMENT ON COLUMN milb_pitcher_pitches.pfx_x IS
'Horizontal movement in inches from pitcher perspective (positive = arm side)';

COMMENT ON COLUMN milb_pitcher_pitches.pfx_z IS
'Vertical movement in inches (positive = rising, negative = dropping)';
