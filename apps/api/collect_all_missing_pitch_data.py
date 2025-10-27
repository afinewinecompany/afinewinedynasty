#!/usr/bin/env python3
"""
Collect all missing pitch data for prospects.
This script identifies and collects pitch-by-pitch data for games that have game logs but no pitch data.
"""

import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime
import time
from typing import List, Dict, Tuple, Optional
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 20,
    DB_URL,
    connect_timeout=30
)

class PitchDataCollector:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            'players_processed': 0,
            'games_processed': 0,
            'pitches_collected': 0,
            'errors': 0,
            'start_time': time.time()
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def get_players_with_missing_data(self) -> List[Dict]:
        """Get all players with game logs but missing pitch data"""
        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Get players with missing pitch data, prioritized by ranking
            query = """
                WITH missing_data AS (
                    SELECT DISTINCT
                        p.id as prospect_id,
                        p.name,
                        p.mlb_player_id,
                        p.position,
                        -- Count missing games
                        COUNT(DISTINCT gl.game_pk) as total_games,
                        COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                        COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
                        -- Get game details
                        array_agg(DISTINCT gl.game_pk)
                            FILTER (WHERE bp.game_pk IS NULL) as missing_game_pks,
                        array_agg(DISTINCT gl.season ORDER BY gl.season DESC) as seasons
                    FROM prospects p
                    INNER JOIN milb_game_logs gl
                        ON p.mlb_player_id::text = gl.mlb_player_id::text
                        AND gl.season IN (2024, 2025)
                        AND gl.plate_appearances > 0
                    LEFT JOIN milb_batter_pitches bp
                        ON gl.game_pk = bp.game_pk
                        AND p.mlb_player_id::integer = bp.mlb_batter_id
                    WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                        AND p.mlb_player_id IS NOT NULL
                    GROUP BY p.id, p.name, p.mlb_player_id, p.position
                    HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
                )
                SELECT
                    prospect_id,
                    name,
                    mlb_player_id::integer as mlb_player_id,
                    position,
                    missing_games,
                    missing_game_pks,
                    seasons
                FROM missing_data
                WHERE missing_games > 0
                ORDER BY
                    CASE WHEN position IN ('SS', 'CF', 'C') THEN 0 ELSE 1 END,  -- Premium positions first
                    missing_games DESC
                LIMIT 200  -- Process top 200 players with most missing data
            """

            cur.execute(query)
            results = cur.fetchall()

            players = []
            for row in results:
                players.append({
                    'prospect_id': row[0],
                    'name': row[1],
                    'mlb_player_id': row[2],
                    'position': row[3],
                    'missing_games': row[4],
                    'missing_game_pks': row[5] if row[5] else [],
                    'seasons': row[6] if row[6] else []
                })

            return players

        finally:
            connection_pool.putconn(conn)

    async def collect_game_pitches(self, batter_id: int, game_pk: int) -> List[Tuple]:
        """Collect all pitches faced by batter in a single game"""
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                # Get game metadata
                game_data = data.get('gameData', {})
                game_date = game_data.get('datetime', {}).get('officialDate')

                # Determine level from game data
                home_league = game_data.get('teams', {}).get('home', {}).get('league', {}).get('name', '')
                away_league = game_data.get('teams', {}).get('away', {}).get('league', {}).get('name', '')

                # Map to our level codes
                level = self.determine_level(home_league, away_league)

                # Get season from game date
                season = int(game_date[:4]) if game_date else None

                all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                game_pitches = []

                for play in all_plays:
                    matchup = play.get('matchup', {})

                    # Only process plays where our batter was batting
                    if matchup.get('batter', {}).get('id') != batter_id:
                        continue

                    pitcher_id = matchup.get('pitcher', {}).get('id')
                    at_bat_index = play.get('atBatIndex', 0)
                    inning = play.get('about', {}).get('inning', 0)
                    is_top_inning = play.get('about', {}).get('isTopInning', True)

                    play_events = play.get('playEvents', [])

                    for i, event in enumerate(play_events):
                        # Check if this is a pitch
                        if not event.get('isPitch'):
                            continue

                        pitch_data = event.get('pitchData', {})
                        details = event.get('details', {})
                        count = event.get('count', {})
                        coordinates = pitch_data.get('coordinates', {})

                        # Create pitch record tuple for milb_batter_pitches table
                        pitch_record = (
                            batter_id,                          # mlb_batter_id
                            pitcher_id,                         # mlb_pitcher_id
                            game_pk,                           # game_pk
                            game_date,                         # game_date
                            season,                            # season
                            level,                             # level
                            inning,                            # inning
                            1 if is_top_inning else 0,        # is_top
                            at_bat_index,                      # at_bat_index
                            i,                                 # pitch_index
                            details.get('type', {}).get('code'),           # pitch_type
                            details.get('type', {}).get('description'),    # pitch_name
                            pitch_data.get('startSpeed'),                  # velocity
                            coordinates.get('pX'),                         # plate_x
                            coordinates.get('pZ'),                         # plate_z
                            pitch_data.get('zone'),                         # zone
                            count.get('balls', 0),                         # balls
                            count.get('strikes', 0),                       # strikes
                            details.get('call', {}).get('code'),           # outcome
                            details.get('call', {}).get('description'),    # description
                            details.get('isInPlay', False),               # is_in_play
                            details.get('isStrike', False),               # is_strike
                            details.get('isBall', False),                 # is_ball
                            pitch_data.get('breaks', {}).get('spinRate'),  # spin_rate
                            pitch_data.get('breaks', {}).get('breakVertical'),    # break_vertical
                            pitch_data.get('breaks', {}).get('breakHorizontal'),  # break_horizontal
                            pitch_data.get('coordinates', {}).get('pfxX'),        # pfx_x
                            pitch_data.get('coordinates', {}).get('pfxZ'),        # pfx_z
                            pitch_data.get('plateTime'),                          # release_extension
                            None,  # exit_velocity (will be updated separately)
                            None,  # launch_angle
                            None,  # hit_distance
                            None   # hard_hit
                        )

                        game_pitches.append(pitch_record)

                return game_pitches

        except asyncio.TimeoutError:
            logger.warning(f"Timeout collecting game {game_pk} for batter {batter_id}")
        except Exception as e:
            logger.error(f"Error collecting game {game_pk} for batter {batter_id}: {str(e)}")

        return []

    def determine_level(self, home_league: str, away_league: str) -> str:
        """Determine the level code from league names"""
        leagues = [home_league.upper(), away_league.upper()]

        for league in leagues:
            if 'TRIPLE' in league or 'AAA' in league:
                return 'AAA'
            elif 'DOUBLE' in league or 'SOUTHERN' in league or 'EASTERN' in league or 'TEXAS' in league:
                return 'AA'
            elif 'HIGH-A' in league or 'HIGH A' in league:
                return 'A+'
            elif 'SINGLE-A' in league or 'SINGLE A' in league or 'LOW-A' in league:
                return 'A'
            elif 'ROOKIE' in league or 'COMPLEX' in league or 'DSL' in league or 'FCL' in league:
                return 'R'

        return 'A'  # Default

    def save_pitches(self, pitches: List[Tuple]) -> int:
        """Save pitches to database"""
        if not pitches:
            return 0

        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Insert pitches
            insert_query = """
                INSERT INTO milb_batter_pitches (
                    mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level,
                    inning, is_top, at_bat_index, pitch_index,
                    pitch_type, pitch_name, velocity, plate_x, plate_z, zone,
                    balls, strikes, outcome, description,
                    is_in_play, is_strike, is_ball,
                    spin_rate, break_vertical, break_horizontal, pfx_x, pfx_z,
                    release_extension, exit_velocity, launch_angle, hit_distance, hard_hit
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_index)
                DO NOTHING
            """

            cur.executemany(insert_query, pitches)
            conn.commit()

            return cur.rowcount

        except Exception as e:
            logger.error(f"Error saving pitches: {str(e)}")
            conn.rollback()
            return 0
        finally:
            connection_pool.putconn(conn)

    async def process_player(self, player: Dict) -> Dict:
        """Process all missing games for a player"""
        player_name = player['name']
        batter_id = player['mlb_player_id']
        missing_game_pks = player['missing_game_pks']

        logger.info(f"Processing {player_name} - {len(missing_game_pks)} missing games")

        total_pitches = 0
        games_collected = 0

        # Process games in batches to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(missing_game_pks), batch_size):
            batch = missing_game_pks[i:i + batch_size]

            tasks = [self.collect_game_pitches(batter_id, game_pk) for game_pk in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing game: {str(result)}")
                    self.stats['errors'] += 1
                elif result:
                    pitches_saved = self.save_pitches(result)
                    if pitches_saved > 0:
                        total_pitches += pitches_saved
                        games_collected += 1
                        self.stats['pitches_collected'] += pitches_saved

            # Rate limit between batches
            await asyncio.sleep(1)

        self.stats['games_processed'] += games_collected

        logger.info(f"  Completed {player_name}: {games_collected}/{len(missing_game_pks)} games, {total_pitches} pitches")

        return {
            'name': player_name,
            'games_collected': games_collected,
            'pitches_collected': total_pitches
        }

    async def run_collection(self):
        """Main collection process"""
        logger.info("=" * 80)
        logger.info("STARTING COMPREHENSIVE PITCH DATA COLLECTION")
        logger.info("=" * 80)

        # Get all players with missing data
        players = self.get_players_with_missing_data()

        if not players:
            logger.info("No players with missing pitch data found")
            return

        logger.info(f"Found {len(players)} players with missing pitch data")
        logger.info("Top 10 players with most missing games:")
        for player in players[:10]:
            logger.info(f"  {player['name']}: {player['missing_games']} games missing")

        # Process players
        for player in players:
            self.stats['players_processed'] += 1
            await self.process_player(player)

            # Show progress every 10 players
            if self.stats['players_processed'] % 10 == 0:
                elapsed = time.time() - self.stats['start_time']
                logger.info(f"\nProgress: {self.stats['players_processed']}/{len(players)} players")
                logger.info(f"  Games: {self.stats['games_processed']}, Pitches: {self.stats['pitches_collected']}")
                logger.info(f"  Time elapsed: {elapsed:.1f}s")

        # Final summary
        elapsed = time.time() - self.stats['start_time']
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Players processed: {self.stats['players_processed']}")
        logger.info(f"Games collected: {self.stats['games_processed']}")
        logger.info(f"Pitches collected: {self.stats['pitches_collected']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Total time: {elapsed:.1f} seconds")

        # Save summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = f"pitch_collection_summary_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'stats': self.stats,
                'players_processed': self.stats['players_processed'],
                'runtime_seconds': elapsed
            }, f, indent=2)

        logger.info(f"Summary saved to: {summary_file}")

async def main():
    """Main entry point"""
    async with PitchDataCollector() as collector:
        await collector.run_collection()

if __name__ == "__main__":
    asyncio.run(main())