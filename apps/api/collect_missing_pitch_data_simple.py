#!/usr/bin/env python3
"""
Simplified pitch collection for missing data - matches actual table schema.
"""

import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime
import time
from typing import List, Dict, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
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

class SimplePitchCollector:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            'players_processed': 0,
            'games_processed': 0,
            'pitches_collected': 0,
            'start_time': time.time()
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def get_priority_players(self) -> List[Dict]:
        """Get priority players - start with Leo De Vries and other critical cases"""
        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Get players with most missing pitch data in 2025
            query = """
                WITH missing_data AS (
                    SELECT
                        p.name,
                        p.mlb_player_id::integer as mlb_player_id,
                        COUNT(DISTINCT gl.game_pk) as total_games,
                        COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                        array_agg(gl.game_pk) FILTER (WHERE bp.game_pk IS NULL) as missing_games
                    FROM prospects p
                    INNER JOIN milb_game_logs gl
                        ON p.mlb_player_id::text = gl.mlb_player_id::text
                        AND gl.season = 2025
                        AND gl.plate_appearances > 0
                    LEFT JOIN milb_batter_pitches bp
                        ON gl.game_pk = bp.game_pk
                        AND p.mlb_player_id::integer = bp.mlb_batter_id
                    WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH')
                        AND p.mlb_player_id IS NOT NULL
                    GROUP BY p.name, p.mlb_player_id
                    HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
                )
                SELECT
                    name,
                    mlb_player_id,
                    total_games,
                    games_with_pitches,
                    total_games - games_with_pitches as missing_count,
                    missing_games
                FROM missing_data
                ORDER BY
                    CASE WHEN name = 'Leo De Vries' THEN 0 ELSE 1 END,  -- Leo first
                    missing_count DESC
                LIMIT 50  -- Top 50 players
            """

            cur.execute(query)
            results = cur.fetchall()

            players = []
            for row in results:
                players.append({
                    'name': row[0],
                    'mlb_player_id': row[1],
                    'total_games': row[2],
                    'games_with_pitches': row[3],
                    'missing_count': row[4],
                    'missing_games': row[5] if row[5] else []
                })

            return players

        finally:
            connection_pool.putconn(conn)

    async def collect_game_pitches(self, batter_id: int, game_pk: int) -> List[Dict]:
        """Collect pitch data for a single game"""
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                # Get game date and determine level
                game_date = data.get('gameData', {}).get('datetime', {}).get('officialDate')
                season = int(game_date[:4]) if game_date else 2025

                # Determine level from game data
                home_team = data.get('gameData', {}).get('teams', {}).get('home', {})
                away_team = data.get('gameData', {}).get('teams', {}).get('away', {})
                level = self.determine_level(home_team, away_team)

                all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                pitches = []
                for play in all_plays:
                    matchup = play.get('matchup', {})

                    # Only process plays where our batter was batting
                    if matchup.get('batter', {}).get('id') != batter_id:
                        continue

                    pitcher_id = matchup.get('pitcher', {}).get('id')
                    at_bat_index = play.get('atBatIndex', 0)
                    inning = play.get('about', {}).get('inning', 0)

                    play_events = play.get('playEvents', [])

                    for pitch_index, event in enumerate(play_events):
                        if not event.get('isPitch'):
                            continue

                        pitch_data = event.get('pitchData', {})
                        details = event.get('details', {})

                        # Extract exit velocity if available
                        exit_velocity = None
                        launch_angle = None
                        hit_distance = None
                        hit_data = event.get('hitData', {})
                        if hit_data:
                            exit_velocity = hit_data.get('launchSpeed')
                            launch_angle = hit_data.get('launchAngle')
                            hit_distance = hit_data.get('totalDistance')

                        pitches.append({
                            'mlb_batter_id': batter_id,
                            'mlb_pitcher_id': pitcher_id,
                            'game_pk': game_pk,
                            'game_date': game_date,
                            'season': season,
                            'level': level,
                            'inning': inning,
                            'at_bat_index': at_bat_index,
                            'pitch_index': pitch_index,
                            'pitch_type': details.get('type', {}).get('code'),
                            'velocity': pitch_data.get('startSpeed'),
                            'exit_velocity': exit_velocity,
                            'launch_angle': launch_angle,
                            'hit_distance': hit_distance
                        })

                return pitches

        except asyncio.TimeoutError:
            logger.warning(f"Timeout for game {game_pk}")
        except Exception as e:
            logger.error(f"Error for game {game_pk}: {str(e)}")

        return []

    def determine_level(self, home_team: Dict, away_team: Dict) -> str:
        """Determine level from team data"""
        # Check parent org names
        for team in [home_team, away_team]:
            parent = team.get('parentOrgName', '').upper()
            league = team.get('league', {}).get('name', '').upper()

            if 'TRIPLE' in league or 'AAA' in league:
                return 'AAA'
            elif 'DOUBLE' in league or 'AA' in league:
                return 'AA'
            elif 'HIGH-A' in league or 'HIGH A' in league:
                return 'A+'
            elif 'SINGLE-A' in league or 'SINGLE A' in league:
                return 'A'

        return 'A'  # Default

    def save_pitches_batch(self, pitches: List[Dict]) -> int:
        """Save pitches to database"""
        if not pitches:
            return 0

        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Prepare data for insertion
            insert_data = []
            for p in pitches:
                insert_data.append((
                    p['mlb_batter_id'],
                    p['mlb_pitcher_id'],
                    p['game_pk'],
                    p['game_date'],
                    p['season'],
                    p['level'],
                    p['inning'],
                    p['at_bat_index'],
                    p['pitch_index'],
                    p['pitch_type'],
                    p['velocity'],
                    p['exit_velocity'],
                    p['launch_angle'],
                    p['hit_distance']
                ))

            # Insert with conflict handling
            insert_query = """
                INSERT INTO milb_batter_pitches (
                    mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level,
                    inning, at_bat_index, pitch_index, pitch_type, velocity,
                    exit_velocity, launch_angle, hit_distance
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_index)
                DO NOTHING
            """

            cur.executemany(insert_query, insert_data)
            conn.commit()

            return cur.rowcount

        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            conn.rollback()
            return 0
        finally:
            connection_pool.putconn(conn)

    async def process_player(self, player: Dict):
        """Process all missing games for a player"""
        name = player['name']
        batter_id = player['mlb_player_id']
        missing_games = player['missing_games']

        logger.info(f"Processing {name}: {len(missing_games)} missing games")

        # Process in batches
        batch_size = 5
        total_pitches = 0

        for i in range(0, len(missing_games), batch_size):
            batch = missing_games[i:i + batch_size]

            # Collect games in parallel
            tasks = [self.collect_game_pitches(batter_id, game_pk) for game_pk in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten and save
            all_pitches = []
            for result in results:
                if isinstance(result, list):
                    all_pitches.extend(result)

            if all_pitches:
                saved = self.save_pitches_batch(all_pitches)
                total_pitches += saved
                self.stats['pitches_collected'] += saved

            self.stats['games_processed'] += len(batch)

            # Rate limit
            await asyncio.sleep(0.5)

        logger.info(f"  Completed {name}: {total_pitches} pitches collected")

    async def run_collection(self):
        """Main collection process"""
        logger.info("=" * 80)
        logger.info("STARTING PITCH DATA COLLECTION FOR MISSING GAMES")
        logger.info("=" * 80)

        players = self.get_priority_players()

        if not players:
            logger.info("No players with missing data found")
            return

        logger.info(f"Found {len(players)} players with missing pitch data")
        logger.info("\nTop players with missing games:")
        for p in players[:10]:
            logger.info(f"  {p['name']}: {p['missing_count']} games missing "
                       f"({p['games_with_pitches']}/{p['total_games']} have data)")

        # Process each player
        for player in players:
            self.stats['players_processed'] += 1
            await self.process_player(player)

            # Progress update
            if self.stats['players_processed'] % 5 == 0:
                elapsed = time.time() - self.stats['start_time']
                logger.info(f"\nProgress: {self.stats['players_processed']}/{len(players)} players")
                logger.info(f"  Pitches collected: {self.stats['pitches_collected']}")
                logger.info(f"  Time: {elapsed:.1f}s")

        # Final summary
        elapsed = time.time() - self.stats['start_time']
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Players processed: {self.stats['players_processed']}")
        logger.info(f"Games processed: {self.stats['games_processed']}")
        logger.info(f"Pitches collected: {self.stats['pitches_collected']}")
        logger.info(f"Total time: {elapsed:.1f} seconds")

async def main():
    """Main entry point"""
    async with SimplePitchCollector() as collector:
        await collector.run_collection()

if __name__ == "__main__":
    asyncio.run(main())