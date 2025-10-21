import psycopg2
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def create_pitcher_appearances_table():
    """Create milb_pitcher_appearances table"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("Creating milb_pitcher_appearances table...")

    # Create table
    cur.execute("""
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
            decision VARCHAR(10),

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Constraints
            UNIQUE(mlb_player_id, game_pk, season)
        )
    """)

    logging.info("Creating indexes...")

    # Create indexes
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_player_season
            ON milb_pitcher_appearances(mlb_player_id, season)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_game
            ON milb_pitcher_appearances(game_pk)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pitcher_appearances_season_level
            ON milb_pitcher_appearances(season, level)
    """)

    conn.commit()
    logging.info("Table created successfully!")

    # Verify
    cur.execute("""
        SELECT COUNT(*) FROM milb_pitcher_appearances
    """)
    count = cur.fetchone()[0]
    logging.info(f"Current row count: {count}")

    conn.close()

if __name__ == "__main__":
    create_pitcher_appearances_table()
