-- ============================================================================
-- PITCH-BY-PITCH DATABASE SCHEMA FOR BATTERS AND PITCHERS
-- ============================================================================
-- Stores detailed pitch-level data for both batters and pitchers
-- Each pitch contains both batter-perspective and pitcher-perspective data
-- ============================================================================

-- ============================================================================
-- TABLE 1: BATTER PITCH-BY-PITCH DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS milb_batter_pitches (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Player & Game Identification
    mlb_batter_id INTEGER NOT NULL,               -- MLB Stats API batter ID
    mlb_pitcher_id INTEGER NOT NULL,              -- MLB Stats API pitcher ID (opponent)
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

    -- Release Point (from pitcher)
    release_pos_x FLOAT,                          -- Horizontal release position
    release_pos_y FLOAT,                          -- Distance from rubber (feet)
    release_pos_z FLOAT,                          -- Vertical release height
    release_extension FLOAT,                      -- Extension toward plate (feet)

    -- Spin Metrics
    spin_rate FLOAT,                              -- Spin rate (rpm)
    spin_direction FLOAT,                         -- Spin axis (degrees)

    -- Pitch Location (batter's perspective)
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

    -- Swing/Contact Metrics
    swing BOOLEAN,                                -- Did batter swing?
    contact BOOLEAN,                              -- Did batter make contact?
    swing_and_miss BOOLEAN,                       -- Swinging strike?
    foul BOOLEAN,                                 -- Foul ball?

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
    hit_location INTEGER,                         -- Field location (1-9)
    coord_x FLOAT,                                -- X coordinate of hit
    coord_y FLOAT,                                -- Y coordinate of hit

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint
    UNIQUE(mlb_batter_id, game_pk, at_bat_index, pitch_number)
);

-- ============================================================================
-- TABLE 2: PITCHER PITCH-BY-PITCH DATA
-- ============================================================================

CREATE TABLE IF NOT EXISTS milb_pitcher_pitches (
    -- Primary Key
    id SERIAL PRIMARY KEY,

    -- Player & Game Identification
    mlb_pitcher_id INTEGER NOT NULL,              -- MLB Stats API pitcher ID
    mlb_batter_id INTEGER NOT NULL,               -- MLB Stats API batter ID (opponent)
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

    -- Swing/Contact Metrics (batter outcome)
    swing BOOLEAN,                                -- Did batter swing?
    contact BOOLEAN,                              -- Did batter make contact?
    swing_and_miss BOOLEAN,                       -- Swinging strike?
    foul BOOLEAN,                                 -- Foul ball?

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

    -- Unique constraint
    UNIQUE(mlb_pitcher_id, game_pk, at_bat_index, pitch_number)
);

-- ============================================================================
-- INDEXES FOR BATTER PITCHES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_batter_pitches_batter ON milb_batter_pitches(mlb_batter_id);
CREATE INDEX IF NOT EXISTS idx_batter_pitches_season ON milb_batter_pitches(season);
CREATE INDEX IF NOT EXISTS idx_batter_pitches_batter_season ON milb_batter_pitches(mlb_batter_id, season);
CREATE INDEX IF NOT EXISTS idx_batter_pitches_game ON milb_batter_pitches(game_pk);
CREATE INDEX IF NOT EXISTS idx_batter_pitches_type ON milb_batter_pitches(pitch_type) WHERE pitch_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batter_pitches_velocity ON milb_batter_pitches(start_speed) WHERE start_speed IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_batter_pitches_launch ON milb_batter_pitches(launch_speed, launch_angle) WHERE launch_speed IS NOT NULL;

-- ============================================================================
-- INDEXES FOR PITCHER PITCHES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher ON milb_pitcher_pitches(mlb_pitcher_id);
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_season ON milb_pitcher_pitches(season);
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_pitcher_season ON milb_pitcher_pitches(mlb_pitcher_id, season);
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_game ON milb_pitcher_pitches(game_pk);
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_type ON milb_pitcher_pitches(pitch_type) WHERE pitch_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_velocity ON milb_pitcher_pitches(start_speed) WHERE start_speed IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pitcher_pitches_launch ON milb_pitcher_pitches(launch_speed, launch_angle) WHERE launch_speed IS NOT NULL;

-- ============================================================================
-- SUMMARY VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW batter_pitch_summary AS
SELECT
    mlb_batter_id,
    season,
    level,
    COUNT(DISTINCT game_pk) as games,
    COUNT(*) as pitches_seen,
    COUNT(DISTINCT at_bat_index || '-' || game_pk) as plate_appearances,

    -- Pitch Recognition
    AVG(start_speed) as avg_pitch_speed_faced,
    COUNT(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN 1 END) as fastballs_faced,
    COUNT(CASE WHEN pitch_type IN ('SL', 'SV') THEN 1 END) as sliders_faced,
    COUNT(CASE WHEN pitch_type IN ('CH', 'FS') THEN 1 END) as changeups_faced,

    -- Swing Decisions
    COUNT(CASE WHEN swing THEN 1 END) as swings,
    COUNT(CASE WHEN contact THEN 1 END) as contacts,
    COUNT(CASE WHEN swing_and_miss THEN 1 END) as whiffs,
    ROUND(COUNT(CASE WHEN contact THEN 1 END)::NUMERIC /
          NULLIF(COUNT(CASE WHEN swing THEN 1 END), 0) * 100, 1) as contact_pct,
    ROUND(COUNT(CASE WHEN swing_and_miss THEN 1 END)::NUMERIC /
          NULLIF(COUNT(CASE WHEN swing THEN 1 END), 0) * 100, 1) as whiff_pct,

    -- Batted Ball
    COUNT(CASE WHEN launch_speed IS NOT NULL THEN 1 END) as balls_in_play,
    AVG(launch_speed) as avg_exit_velo,
    AVG(launch_angle) as avg_launch_angle,
    COUNT(CASE WHEN launch_speed >= 95 THEN 1 END) as hard_hit_balls,

    -- Outcomes
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Strikeout%' THEN 1 END) as strikeouts,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Walk%' THEN 1 END) as walks,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Home Run%' THEN 1 END) as home_runs

FROM milb_batter_pitches
GROUP BY mlb_batter_id, season, level;

CREATE OR REPLACE VIEW pitcher_pitch_summary AS
SELECT
    mlb_pitcher_id,
    season,
    level,
    COUNT(DISTINCT game_pk) as games_pitched,
    COUNT(*) as total_pitches,
    COUNT(DISTINCT at_bat_index || '-' || game_pk) as batters_faced,

    -- Pitch Mix
    ROUND(COUNT(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN 1 END)::NUMERIC /
          NULLIF(COUNT(*), 0) * 100, 1) as fastball_pct,
    ROUND(COUNT(CASE WHEN pitch_type IN ('SL', 'SV') THEN 1 END)::NUMERIC /
          NULLIF(COUNT(*), 0) * 100, 1) as slider_pct,
    ROUND(COUNT(CASE WHEN pitch_type IN ('CH', 'FS') THEN 1 END)::NUMERIC /
          NULLIF(COUNT(*), 0) * 100, 1) as changeup_pct,

    -- Velocity
    AVG(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN start_speed END) as avg_fb_velo,
    MAX(start_speed) as max_velo,

    -- Spin
    AVG(CASE WHEN pitch_type LIKE 'FF%' OR pitch_type = 'FA' THEN spin_rate END) as avg_fb_spin,

    -- Command
    ROUND(COUNT(CASE WHEN is_strike THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as strike_pct,
    ROUND(COUNT(CASE WHEN zone BETWEEN 1 AND 9 THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 1) as zone_pct,

    -- Stuff
    COUNT(CASE WHEN swing_and_miss THEN 1 END) as whiffs,
    ROUND(COUNT(CASE WHEN swing_and_miss THEN 1 END)::NUMERIC /
          NULLIF(COUNT(CASE WHEN swing THEN 1 END), 0) * 100, 1) as whiff_pct,

    -- Results
    AVG(launch_speed) as avg_exit_velo_allowed,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Strikeout%' THEN 1 END) as strikeouts,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Walk%' THEN 1 END) as walks,
    COUNT(CASE WHEN is_final_pitch AND pa_result LIKE '%Home Run%' THEN 1 END) as home_runs_allowed

FROM milb_pitcher_pitches
GROUP BY mlb_pitcher_id, season, level;
