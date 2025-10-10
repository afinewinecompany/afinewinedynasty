"""
Collect MLB Statcast data for all prospects.

This script collects comprehensive Statcast metrics for both hitters and pitchers
who have MiLB data in our database.

For Hitters:
- Exit velocity, launch angle, distance
- Barrel%, Hard Hit%, Sweet Spot%
- Sprint speed, bat speed, swing length

For Pitchers:
- Pitch velocity, spin rate, release point
- Pitch movement (horizontal/vertical break)
- Pitch type usage
- Whiff%, Chase%, In-Zone%

Data Source: Baseball Savant via pybaseball library
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Tuple, Optional
import pandas as pd
from sqlalchemy import text
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pybaseball import statcast_batter, statcast_pitcher, cache
except ImportError:
    print("ERROR: pybaseball not installed. Run: pip install pybaseball")
    exit(1)

from app.db.database import engine

# Enable pybaseball caching to speed up repeated queries
cache.enable()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLBStatcastCollector:
    """Collect MLB Statcast data for prospects."""

    def __init__(self, seasons: List[int]):
        self.seasons = seasons
        self.players_processed = 0
        self.hitters_collected = 0
        self.pitchers_collected = 0
        self.errors = []

    async def get_prospects_with_positions(self) -> List[Tuple[int, str, int]]:
        """
        Get all unique MLB player IDs from milb_game_logs with their positions.

        Returns list of (mlb_player_id, position, milb_games).
        """
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                WITH player_positions AS (
                    SELECT
                        mlb_player_id,
                        -- Determine if pitcher based on games pitched
                        CASE
                            WHEN SUM(games_pitched) > 0 THEN 'P'
                            ELSE 'H'  -- Hitter
                        END as position_type,
                        COUNT(*) as milb_games
                    FROM milb_game_logs
                    WHERE mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                )
                SELECT mlb_player_id, position_type, milb_games
                FROM player_positions
                ORDER BY milb_games DESC
            """))

            players = [(row[0], row[1], row[2]) for row in result.fetchall()]

        logger.info(f"Found {len(players)} prospects to collect Statcast data for")
        logger.info(f"  Hitters: {sum(1 for p in players if p[1] == 'H')}")
        logger.info(f"  Pitchers: {sum(1 for p in players if p[1] == 'P')}")

        return players

    async def check_existing_data(self, player_id: int, season: int, data_type: str) -> bool:
        """Check if we already have Statcast data for this player/season."""
        table_name = 'mlb_statcast_hitting' if data_type == 'H' else 'mlb_statcast_pitching'

        try:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM {table_name}
                        WHERE mlb_player_id = :player_id
                        AND season = :season
                    """),
                    {'player_id': player_id, 'season': season}
                )

                count = result.scalar()
                return count > 0
        except Exception:
            # Table doesn't exist yet, so no existing data
            return False

    def collect_hitting_statcast(self, player_id: int, season: int) -> Optional[pd.DataFrame]:
        """
        Collect hitting Statcast data for a player/season using pybaseball.

        Returns DataFrame with batted ball events or None if no data.
        """
        try:
            start_date = f'{season}-03-01'
            end_date = f'{season}-11-01'

            logger.debug(f"Fetching hitting Statcast for player {player_id}, season {season}")

            df = statcast_batter(start_date, end_date, player_id)

            if df is None or len(df) == 0:
                return None

            # Add metadata
            df['mlb_player_id'] = player_id
            df['season'] = season

            return df

        except Exception as e:
            logger.error(f"Error collecting hitting for player {player_id}, season {season}: {e}")
            self.errors.append((player_id, season, 'hitting', str(e)))
            return None

    def collect_pitching_statcast(self, player_id: int, season: int) -> Optional[pd.DataFrame]:
        """
        Collect pitching Statcast data for a player/season using pybaseball.

        Returns DataFrame with pitch events or None if no data.
        """
        try:
            start_date = f'{season}-03-01'
            end_date = f'{season}-11-01'

            logger.debug(f"Fetching pitching Statcast for player {player_id}, season {season}")

            df = statcast_pitcher(start_date, end_date, player_id)

            if df is None or len(df) == 0:
                return None

            # Add metadata
            df['mlb_player_id'] = player_id
            df['season'] = season

            return df

        except Exception as e:
            logger.error(f"Error collecting pitching for player {player_id}, season {season}: {e}")
            self.errors.append((player_id, season, 'pitching', str(e)))
            return None

    async def save_hitting_statcast(self, df: pd.DataFrame):
        """Save hitting Statcast data to database."""
        if df is None or len(df) == 0:
            return

        # Select relevant columns (pybaseball returns 80+ columns)
        hitting_cols = [
            'mlb_player_id', 'season', 'game_date', 'pitch_type',
            'release_speed', 'release_pos_x', 'release_pos_z',
            'events', 'description', 'zone',
            'stand', 'p_throws',
            'home_team', 'away_team',
            'type',  # B, S, X (ball, strike, in play)
            'hit_location', 'bb_type',  # batted ball type
            'balls', 'strikes', 'pfx_x', 'pfx_z',  # pitch movement
            'plate_x', 'plate_z',  # pitch location
            'on_3b', 'on_2b', 'on_1b',
            'outs_when_up', 'inning', 'inning_topbot',
            'hc_x', 'hc_y',  # hit coordinates
            'fielder_2', 'fielder_3', 'fielder_4', 'fielder_5', 'fielder_6',
            'fielder_7', 'fielder_8', 'fielder_9',
            'sv_id',  # Unique pitch ID
            # STATCAST METRICS (the important ones!)
            'launch_speed', 'launch_angle', 'hit_distance_sc',
            'estimated_ba_using_speedangle', 'estimated_woba_using_speedangle',
            'woba_value', 'woba_denom', 'babip_value',
            'iso_value', 'launch_speed_angle',
            'at_bat_number', 'pitch_number'
        ]

        # Only keep columns that exist
        available_cols = [col for col in hitting_cols if col in df.columns]
        df_clean = df[available_cols].copy()

        # Convert game_date to date
        df_clean['game_date'] = pd.to_datetime(df_clean['game_date']).dt.date

        # Create table if needed
        await self.create_hitting_table()

        # Insert data
        rows_inserted = 0
        async with engine.begin() as conn:
            for _, row in df_clean.iterrows():
                # Convert row to dict, handling NaN values
                record = row.to_dict()
                record = {k: (None if pd.isna(v) else v) for k, v in record.items()}

                try:
                    await conn.execute(text("""
                        INSERT INTO mlb_statcast_hitting
                        (mlb_player_id, season, game_date, pitch_type, release_speed,
                         events, description, zone, stand, p_throws,
                         home_team, away_team, type, hit_location, bb_type,
                         balls, strikes, plate_x, plate_z,
                         hc_x, hc_y, launch_speed, launch_angle, hit_distance_sc,
                         estimated_ba_using_speedangle, estimated_woba_using_speedangle,
                         woba_value, launch_speed_angle, sv_id)
                        VALUES
                        (:mlb_player_id, :season, :game_date, :pitch_type, :release_speed,
                         :events, :description, :zone, :stand, :p_throws,
                         :home_team, :away_team, :type, :hit_location, :bb_type,
                         :balls, :strikes, :plate_x, :plate_z,
                         :hc_x, :hc_y, :launch_speed, :launch_angle, :hit_distance_sc,
                         :estimated_ba_using_speedangle, :estimated_woba_using_speedangle,
                         :woba_value, :launch_speed_angle, :sv_id)
                        ON CONFLICT (sv_id) DO NOTHING
                    """), record)

                    rows_inserted += 1

                except Exception as e:
                    if "violates not-null constraint" in str(e) or "column" in str(e):
                        # Skip rows with missing required data
                        continue
                    else:
                        logger.error(f"Error inserting hitting row: {e}")

        logger.info(f"  Inserted {rows_inserted} hitting Statcast events")

    async def save_pitching_statcast(self, df: pd.DataFrame):
        """Save pitching Statcast data to database."""
        if df is None or len(df) == 0:
            return

        # Select relevant columns
        pitching_cols = [
            'mlb_player_id', 'season', 'game_date', 'pitch_type', 'pitch_name',
            'release_speed', 'release_pos_x', 'release_pos_y', 'release_pos_z',
            'release_spin_rate', 'release_extension',
            'events', 'description', 'zone',
            'stand', 'p_throws',
            'home_team', 'away_team',
            'type',
            'balls', 'strikes', 'pfx_x', 'pfx_z',  # pitch movement
            'plate_x', 'plate_z',  # pitch location at plate
            'vx0', 'vy0', 'vz0',  # velocity components
            'ax', 'ay', 'az',  # acceleration components
            'sz_top', 'sz_bot',  # strike zone dimensions
            'effective_speed', 'release_spin_rate',
            'spin_axis',
            # Outcome
            'launch_speed', 'launch_angle', 'hit_distance_sc',
            'estimated_ba_using_speedangle', 'estimated_woba_using_speedangle',
            'woba_value',
            'sv_id'  # Unique pitch ID
        ]

        available_cols = [col for col in pitching_cols if col in df.columns]
        df_clean = df[available_cols].copy()

        df_clean['game_date'] = pd.to_datetime(df_clean['game_date']).dt.date

        # Create table if needed
        await self.create_pitching_table()

        # Insert data
        rows_inserted = 0
        async with engine.begin() as conn:
            for _, row in df_clean.iterrows():
                record = row.to_dict()
                record = {k: (None if pd.isna(v) else v) for k, v in record.items()}

                try:
                    await conn.execute(text("""
                        INSERT INTO mlb_statcast_pitching
                        (mlb_player_id, season, game_date, pitch_type, pitch_name,
                         release_speed, release_pos_x, release_pos_y, release_pos_z,
                         release_spin_rate, release_extension,
                         events, description, zone, stand, p_throws,
                         home_team, away_team, type, balls, strikes,
                         pfx_x, pfx_z, plate_x, plate_z,
                         vx0, vy0, vz0, ax, ay, az,
                         sz_top, sz_bot, effective_speed, spin_axis,
                         launch_speed, launch_angle, hit_distance_sc,
                         estimated_woba_using_speedangle, woba_value, sv_id)
                        VALUES
                        (:mlb_player_id, :season, :game_date, :pitch_type, :pitch_name,
                         :release_speed, :release_pos_x, :release_pos_y, :release_pos_z,
                         :release_spin_rate, :release_extension,
                         :events, :description, :zone, :stand, :p_throws,
                         :home_team, :away_team, :type, :balls, :strikes,
                         :pfx_x, :pfx_z, :plate_x, :plate_z,
                         :vx0, :vy0, :vz0, :ax, :ay, :az,
                         :sz_top, :sz_bot, :effective_speed, :spin_axis,
                         :launch_speed, :launch_angle, :hit_distance_sc,
                         :estimated_woba_using_speedangle, :woba_value, :sv_id)
                        ON CONFLICT (sv_id) DO NOTHING
                    """), record)

                    rows_inserted += 1

                except Exception as e:
                    if "violates not-null constraint" in str(e) or "column" in str(e):
                        continue
                    else:
                        logger.error(f"Error inserting pitching row: {e}")

        logger.info(f"  Inserted {rows_inserted} pitching Statcast events")

    async def create_hitting_table(self):
        """Create mlb_statcast_hitting table if it doesn't exist."""
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mlb_statcast_hitting (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    game_date DATE NOT NULL,
                    sv_id VARCHAR(50) UNIQUE,  -- Savant unique pitch ID

                    -- Pitch Details
                    pitch_type VARCHAR(10),
                    release_speed FLOAT,
                    events VARCHAR(50),  -- Outcome (single, home_run, strikeout, etc.)
                    description VARCHAR(50),  -- ball, called_strike, foul, hit_into_play, etc.
                    zone SMALLINT,
                    stand CHAR(1),  -- L/R batter
                    p_throws CHAR(1),  -- L/R pitcher
                    home_team VARCHAR(10),
                    away_team VARCHAR(10),
                    type CHAR(1),  -- B, S, X

                    -- Batted Ball
                    hit_location SMALLINT,
                    bb_type VARCHAR(20),  -- fly_ball, ground_ball, line_drive, popup
                    balls SMALLINT,
                    strikes SMALLINT,
                    plate_x FLOAT,  -- Pitch location
                    plate_z FLOAT,
                    hc_x FLOAT,  -- Hit coordinates
                    hc_y FLOAT,

                    -- STATCAST METRICS
                    launch_speed FLOAT,  -- Exit velocity
                    launch_angle FLOAT,
                    hit_distance_sc FLOAT,
                    estimated_ba_using_speedangle FLOAT,
                    estimated_woba_using_speedangle FLOAT,
                    woba_value FLOAT,
                    launch_speed_angle SMALLINT,  -- 1-6 classification

                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))

            # Create indexes
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_statcast_hitting_player
                ON mlb_statcast_hitting(mlb_player_id, season)
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_statcast_hitting_date
                ON mlb_statcast_hitting(game_date)
            """))

    async def create_pitching_table(self):
        """Create mlb_statcast_pitching table if it doesn't exist."""
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mlb_statcast_pitching (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    game_date DATE NOT NULL,
                    sv_id VARCHAR(50) UNIQUE,

                    -- Pitch Details
                    pitch_type VARCHAR(10),
                    pitch_name VARCHAR(50),
                    release_speed FLOAT,
                    release_pos_x FLOAT,
                    release_pos_y FLOAT,
                    release_pos_z FLOAT,
                    release_spin_rate FLOAT,
                    release_extension FLOAT,

                    -- Outcome
                    events VARCHAR(50),
                    description VARCHAR(50),
                    zone SMALLINT,
                    stand CHAR(1),
                    p_throws CHAR(1),
                    home_team VARCHAR(10),
                    away_team VARCHAR(10),
                    type CHAR(1),
                    balls SMALLINT,
                    strikes SMALLINT,

                    -- Movement
                    pfx_x FLOAT,  -- Horizontal movement
                    pfx_z FLOAT,  -- Vertical movement (vs gravity)
                    plate_x FLOAT,
                    plate_z FLOAT,

                    -- Physics
                    vx0 FLOAT, vy0 FLOAT, vz0 FLOAT,  -- Velocity
                    ax FLOAT, ay FLOAT, az FLOAT,  -- Acceleration
                    sz_top FLOAT, sz_bot FLOAT,  -- Strike zone
                    effective_speed FLOAT,
                    spin_axis FLOAT,

                    -- Batted Ball (when put in play)
                    launch_speed FLOAT,
                    launch_angle FLOAT,
                    hit_distance_sc FLOAT,
                    estimated_woba_using_speedangle FLOAT,
                    woba_value FLOAT,

                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_statcast_pitching_player
                ON mlb_statcast_pitching(mlb_player_id, season)
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_statcast_pitching_date
                ON mlb_statcast_pitching(game_date)
            """))

    async def collect_for_player(self, player_id: int, position_type: str, milb_games: int):
        """Collect Statcast data for a single player across all seasons."""
        self.players_processed += 1

        total_data_collected = False

        for season in self.seasons:
            # Check if we already have data
            has_data = await self.check_existing_data(player_id, season, position_type)

            if has_data:
                logger.debug(f"  Skipping {player_id} {season} ({position_type}) - already have data")
                continue

            # Collect based on position type
            if position_type == 'H':
                # Hitter
                df = self.collect_hitting_statcast(player_id, season)

                if df is not None and len(df) > 0:
                    await self.save_hitting_statcast(df)
                    self.hitters_collected += 1
                    total_data_collected = True
                    logger.info(f"  [{self.players_processed}] Player {player_id} (H): {len(df)} events in {season}")

            else:
                # Pitcher
                df = self.collect_pitching_statcast(player_id, season)

                if df is not None and len(df) > 0:
                    await self.save_pitching_statcast(df)
                    self.pitchers_collected += 1
                    total_data_collected = True
                    logger.info(f"  [{self.players_processed}] Player {player_id} (P): {len(df)} pitches in {season}")

        if not total_data_collected:
            logger.debug(f"  [{self.players_processed}] Player {player_id}: No MLB Statcast data found")

        # Progress update
        if self.players_processed % 50 == 0:
            logger.info(f"\nProgress: {self.players_processed} players processed")
            logger.info(f"  Hitters with data: {self.hitters_collected}")
            logger.info(f"  Pitchers with data: {self.pitchers_collected}\n")

    async def run(self):
        """Main collection loop."""
        logger.info("=" * 80)
        logger.info("MLB Statcast Collection for Prospects")
        logger.info(f"Seasons: {', '.join(map(str, self.seasons))}")
        logger.info("=" * 80)

        # Create tables first
        logger.info("Creating database tables...")
        await self.create_hitting_table()
        await self.create_pitching_table()
        logger.info("Tables ready\n")

        # Get all prospects
        prospects = await self.get_prospects_with_positions()

        logger.info(f"\nStarting collection for {len(prospects)} prospects...")
        logger.info("")

        # Process each prospect
        for player_id, position_type, milb_games in prospects:
            await self.collect_for_player(player_id, position_type, milb_games)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Prospects processed: {self.players_processed}")
        logger.info(f"Hitters with MLB Statcast: {self.hitters_collected}")
        logger.info(f"Pitchers with MLB Statcast: {self.pitchers_collected}")

        if self.errors:
            logger.warning(f"\nErrors encountered: {len(self.errors)}")
            for player_id, season, data_type, error in self.errors[:10]:
                logger.warning(f"  Player {player_id}, {season}, {data_type}: {error}")

        logger.info("=" * 80)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Collect MLB Statcast data for prospects')
    parser.add_argument('--seasons', type=int, nargs='+', default=[2025, 2024, 2023, 2022, 2021],
                       help='Seasons to collect (default: 2025 2024 2023 2022 2021)')
    args = parser.parse_args()

    collector = MLBStatcastCollector(seasons=args.seasons)
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
