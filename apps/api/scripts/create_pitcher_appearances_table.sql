-- Create table for pitcher game-by-game appearances (analogous to milb_plate_appearances for batters)
CREATE TABLE IF NOT EXISTS milb_pitcher_appearances (
    id SERIAL PRIMARY KEY,
    mlb_player_id INTEGER NOT NULL,
    game_pk BIGINT NOT NULL,
    game_date DATE,
    season INTEGER NOT NULL,
    level VARCHAR(10),

    -- Pitching stats from game log
    innings_pitched DECIMAL(4, 1),
    hits INTEGER,
    runs INTEGER,
    earned_runs INTEGER,
    walks INTEGER,
    strikeouts INTEGER,
    home_runs INTEGER,
    pitches_thrown INTEGER,
    strikes INTEGER,
    balls INTEGER,
    batters_faced INTEGER,

    -- Game context
    team_id INTEGER,
    opponent_id INTEGER,
    is_home BOOLEAN,
    game_type VARCHAR(10),

    -- Result
    decision VARCHAR(10), -- W, L, S, H, BS, etc.

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(mlb_player_id, game_pk, season)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_player_season
    ON milb_pitcher_appearances(mlb_player_id, season);

CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_game
    ON milb_pitcher_appearances(game_pk);

CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_season_level
    ON milb_pitcher_appearances(season, level);

-- Add comment
COMMENT ON TABLE milb_pitcher_appearances IS 'Game-by-game pitching appearances for MiLB prospects';
