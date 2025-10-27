#!/usr/bin/env python3
"""
Final pitch collection script - matches exact table schema for milb_batter_pitches.
Prioritizes Leo De Vries and other players with most missing data.
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

class FinalPitchCollector:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.stats = {
            'players_processed': 0,
            'games_processed': 0,
            'pitches_collected': 0,
            'games_with_data': 0,
            'games_no_data': 0,
            'start_time': time.time()
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def get_priority_players(self) -> List[Dict]:
        """Get priority players with missing pitch data"""
        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Focus on 2025 season with most missing data
            query = """
                WITH missing_data AS (
                    SELECT
                        p.name,
                        p.mlb_player_id::integer as mlb_player_id,
                        p.position,
                        COUNT(DISTINCT gl.game_pk) as total_games,
                        COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                        array_agg(gl.game_pk ORDER BY gl.game_date)
                            FILTER (WHERE bp.game_pk IS NULL) as missing_games,
                        array_agg(gl.game_date ORDER BY gl.game_date)
                            FILTER (WHERE bp.game_pk IS NULL) as missing_dates
                    FROM prospects p
                    INNER JOIN milb_game_logs gl
                        ON p.mlb_player_id::text = gl.mlb_player_id::text
                        AND gl.season = 2025
                        AND gl.plate_appearances > 0
                    LEFT JOIN milb_batter_pitches bp
                        ON gl.game_pk = bp.game_pk
                        AND p.mlb_player_id::integer = bp.mlb_batter_id
                    WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                        AND p.mlb_player_id IS NOT NULL
                    GROUP BY p.name, p.mlb_player_id, p.position
                    HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
                )
                SELECT
                    name,
                    mlb_player_id,
                    position,
                    total_games,
                    games_with_pitches,
                    total_games - games_with_pitches as missing_count,
                    missing_games,
                    missing_dates
                FROM missing_data
                ORDER BY
                    CASE WHEN name = 'Leo De Vries' THEN 0
                         WHEN name = 'Bryce Eldridge' THEN 1
                         ELSE 2 END,  -- Priority players first
                    missing_count DESC
                LIMIT 100  -- Top 100 players
            """

            cur.execute(query)
            results = cur.fetchall()

            players = []
            for row in results:
                players.append({
                    'name': row[0],
                    'mlb_player_id': row[1],
                    'position': row[2],
                    'total_games': row[3],
                    'games_with_pitches': row[4],
                    'missing_count': row[5],
                    'missing_games': row[6] if row[6] else [],
                    'missing_dates': row[7] if row[7] else []
                })

            return players

        finally:
            connection_pool.putconn(conn)

    async def collect_game_pitches(self, batter_id: int, game_pk: int, game_date: str) -> List[Dict]:
        """Collect pitch data for a single game"""
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                # Get game metadata
                game_data = data.get('gameData', {})
                actual_date = game_data.get('datetime', {}).get('officialDate', game_date)
                season = int(actual_date[:4]) if actual_date else 2025

                # Determine level from teams
                home_team = game_data.get('teams', {}).get('home', {})
                away_team = game_data.get('teams', {}).get('away', {})
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
                    half_inning = 'top' if play.get('about', {}).get('isTopInning', True) else 'bottom'

                    # Get at-bat result
                    result = play.get('result', {})
                    pa_result = result.get('type')
                    pa_result_desc = result.get('description', '')

                    play_events = play.get('playEvents', [])
                    pitch_number = 0

                    for event in play_events:
                        if not event.get('isPitch'):
                            continue

                        pitch_number += 1
                        pitch_data = event.get('pitchData', {})
                        details = event.get('details', {})
                        count = event.get('count', {})
                        coordinates = pitch_data.get('coordinates', {})

                        # Hit data if available
                        hit_data = event.get('hitData', {})
                        launch_speed = hit_data.get('launchSpeed') if hit_data else None
                        launch_angle = hit_data.get('launchAngle') if hit_data else None
                        total_distance = hit_data.get('totalDistance') if hit_data else None
                        trajectory = hit_data.get('trajectory') if hit_data else None
                        hardness = hit_data.get('hardness') if hit_data else None
                        coord_x = hit_data.get('coordinates', {}).get('coordX') if hit_data else None
                        coord_y = hit_data.get('coordinates', {}).get('coordY') if hit_data else None

                        # Determine pitch outcomes
                        is_strike = details.get('isStrike', False)
                        is_ball = details.get('isBall', False)
                        is_in_play = details.get('isInPlay', False)
                        call_code = details.get('call', {}).get('code')
                        call_desc = details.get('call', {}).get('description')

                        # Swing/contact info
                        swing = call_code in ['S', 'F', 'X', 'D', 'E', 'T']  # Various swing codes
                        contact = call_code in ['X', 'D', 'E', 'F', 'T']  # In play or foul
                        swing_and_miss = call_code == 'S'  # Swinging strike
                        foul = call_code == 'F'  # Foul ball

                        # Is this the final pitch of the at-bat?
                        is_final = (pitch_number == len([e for e in play_events if e.get('isPitch')]))

                        pitches.append({
                            'mlb_batter_id': batter_id,
                            'mlb_pitcher_id': pitcher_id,
                            'game_pk': game_pk,
                            'game_date': actual_date,
                            'season': season,
                            'level': level,
                            'at_bat_index': at_bat_index,
                            'pitch_number': pitch_number,
                            'inning': inning,
                            'half_inning': half_inning,
                            'pitch_type': details.get('type', {}).get('code'),
                            'pitch_type_description': details.get('type', {}).get('description'),
                            'start_speed': pitch_data.get('startSpeed'),
                            'end_speed': pitch_data.get('endSpeed'),
                            'pfx_x': coordinates.get('pfxX'),
                            'pfx_z': coordinates.get('pfxZ'),
                            'release_pos_x': pitch_data.get('coordinates', {}).get('x0'),
                            'release_pos_y': pitch_data.get('coordinates', {}).get('y0'),
                            'release_pos_z': pitch_data.get('coordinates', {}).get('z0'),
                            'release_extension': pitch_data.get('extension'),
                            'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                            'spin_direction': pitch_data.get('breaks', {}).get('spinDirection'),
                            'plate_x': coordinates.get('pX'),
                            'plate_z': coordinates.get('pZ'),
                            'zone': pitch_data.get('zone'),
                            'pitch_call': call_code,
                            'pitch_result': call_desc,
                            'is_strike': is_strike,
                            'balls': count.get('balls', 0),
                            'strikes': count.get('strikes', 0),
                            'outs': count.get('outs', 0),
                            'swing': swing,
                            'contact': contact,
                            'swing_and_miss': swing_and_miss,
                            'foul': foul,
                            'is_final_pitch': is_final,
                            'pa_result': pa_result if is_final else None,
                            'pa_result_description': pa_result_desc if is_final else None,
                            'launch_speed': launch_speed,
                            'launch_angle': launch_angle,
                            'total_distance': total_distance,
                            'trajectory': trajectory,
                            'hardness': hardness,
                            'hit_location': None,  # Would need to map from coordinates
                            'coord_x': coord_x,
                            'coord_y': coord_y
                        })

                return pitches

        except asyncio.TimeoutError:
            logger.warning(f"Timeout for game {game_pk}")
        except Exception as e:
            logger.error(f"Error for game {game_pk}: {str(e)[:100]}")

        return []

    def determine_level(self, home_team: Dict, away_team: Dict) -> str:
        """Determine level from team data"""
        for team in [home_team, away_team]:
            league = team.get('league', {}).get('name', '').upper()

            if 'TRIPLE' in league or 'AAA' in league or 'PACIFIC' in league or 'INTERNATIONAL' in league:
                return 'AAA'
            elif 'DOUBLE' in league or 'SOUTHERN' in league or 'EASTERN' in league or 'TEXAS' in league:
                return 'AA'
            elif 'HIGH-A' in league or 'HIGH A' in league or 'SOUTH ATLANTIC' in league:
                return 'A+'
            elif 'SINGLE-A' in league or 'SINGLE A' in league or 'CALIFORNIA' in league or 'FLORIDA STATE' in league:
                return 'A'
            elif 'ROOKIE' in league or 'COMPLEX' in league or 'DSL' in league or 'FCL' in league or 'ACL' in league:
                return 'R'

        return 'A'  # Default

    def save_pitches_batch(self, pitches: List[Dict]) -> int:
        """Save pitches to database"""
        if not pitches:
            return 0

        conn = connection_pool.getconn()
        try:
            cur = conn.cursor()

            # Prepare data - all columns in order
            insert_data = []
            for p in pitches:
                insert_data.append((
                    p['mlb_batter_id'], p['mlb_pitcher_id'], p['game_pk'], p['game_date'],
                    p['season'], p['level'], p['at_bat_index'], p['pitch_number'],
                    p['inning'], p['half_inning'], p['pitch_type'], p['pitch_type_description'],
                    p['start_speed'], p['end_speed'], p['pfx_x'], p['pfx_z'],
                    p['release_pos_x'], p['release_pos_y'], p['release_pos_z'], p['release_extension'],
                    p['spin_rate'], p['spin_direction'], p['plate_x'], p['plate_z'],
                    p['zone'], p['pitch_call'], p['pitch_result'], p['is_strike'],
                    p['balls'], p['strikes'], p['outs'], p['swing'],
                    p['contact'], p['swing_and_miss'], p['foul'], p['is_final_pitch'],
                    p['pa_result'], p['pa_result_description'], p['launch_speed'], p['launch_angle'],
                    p['total_distance'], p['trajectory'], p['hardness'], p['hit_location'],
                    p['coord_x'], p['coord_y']
                ))

            # Insert with conflict handling
            insert_query = """
                INSERT INTO milb_batter_pitches (
                    mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level,
                    at_bat_index, pitch_number, inning, half_inning, pitch_type, pitch_type_description,
                    start_speed, end_speed, pfx_x, pfx_z,
                    release_pos_x, release_pos_y, release_pos_z, release_extension,
                    spin_rate, spin_direction, plate_x, plate_z,
                    zone, pitch_call, pitch_result, is_strike,
                    balls, strikes, outs, swing,
                    contact, swing_and_miss, foul, is_final_pitch,
                    pa_result, pa_result_description, launch_speed, launch_angle,
                    total_distance, trajectory, hardness, hit_location,
                    coord_x, coord_y
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                DO NOTHING
            """

            cur.executemany(insert_query, insert_data)
            conn.commit()

            return cur.rowcount

        except Exception as e:
            logger.error(f"Database error: {str(e)[:200]}")
            conn.rollback()
            return 0
        finally:
            connection_pool.putconn(conn)

    async def process_player(self, player: Dict):
        """Process all missing games for a player"""
        name = player['name']
        batter_id = player['mlb_player_id']
        missing_games = player['missing_games']
        missing_dates = player['missing_dates']

        logger.info(f"Processing {name} ({player['position']}): {len(missing_games)} missing games")

        # Process in small batches
        batch_size = 3
        total_pitches = 0
        games_with_data = 0

        for i in range(0, len(missing_games), batch_size):
            batch_games = missing_games[i:i + batch_size]
            batch_dates = missing_dates[i:i + batch_size]

            # Collect games in parallel
            tasks = []
            for game_pk, game_date in zip(batch_games, batch_dates):
                tasks.append(self.collect_game_pitches(batter_id, game_pk, game_date))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            all_pitches = []
            for result in results:
                if isinstance(result, list) and len(result) > 0:
                    all_pitches.extend(result)
                    games_with_data += 1
                    self.stats['games_with_data'] += 1
                else:
                    self.stats['games_no_data'] += 1

            # Save pitches
            if all_pitches:
                saved = self.save_pitches_batch(all_pitches)
                total_pitches += saved
                self.stats['pitches_collected'] += saved

            self.stats['games_processed'] += len(batch_games)

            # Brief pause between batches
            await asyncio.sleep(0.3)

        logger.info(f"  Completed {name}: {games_with_data}/{len(missing_games)} games had data, "
                   f"{total_pitches} pitches collected")

    async def run_collection(self):
        """Main collection process"""
        logger.info("=" * 80)
        logger.info("STARTING FINAL PITCH DATA COLLECTION")
        logger.info("=" * 80)

        players = self.get_priority_players()

        if not players:
            logger.info("No players with missing data found")
            return

        logger.info(f"Found {len(players)} players with missing pitch data in 2025")
        logger.info("\nTop priority players:")
        for p in players[:10]:
            coverage = (p['games_with_pitches'] / p['total_games'] * 100) if p['total_games'] > 0 else 0
            logger.info(f"  {p['name']:<25} {p['position']:<3}: {p['missing_count']:>3} games missing "
                       f"({coverage:>5.1f}% coverage)")

        # Process each player
        for idx, player in enumerate(players, 1):
            self.stats['players_processed'] += 1
            await self.process_player(player)

            # Progress update every 5 players
            if idx % 5 == 0:
                elapsed = time.time() - self.stats['start_time']
                rate = self.stats['pitches_collected'] / elapsed if elapsed > 0 else 0
                logger.info(f"\n--- Progress: {idx}/{len(players)} players ---")
                logger.info(f"  Pitches collected: {self.stats['pitches_collected']:,}")
                logger.info(f"  Games with data: {self.stats['games_with_data']}")
                logger.info(f"  Games without data: {self.stats['games_no_data']}")
                logger.info(f"  Collection rate: {rate:.1f} pitches/sec")
                logger.info(f"  Time elapsed: {elapsed:.1f}s\n")

        # Final summary
        elapsed = time.time() - self.stats['start_time']
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Players processed: {self.stats['players_processed']}")
        logger.info(f"Games processed: {self.stats['games_processed']}")
        logger.info(f"Games with data: {self.stats['games_with_data']}")
        logger.info(f"Games without data: {self.stats['games_no_data']}")
        logger.info(f"Pitches collected: {self.stats['pitches_collected']:,}")
        logger.info(f"Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        logger.info(f"Average: {self.stats['pitches_collected']/elapsed:.1f} pitches/sec")

        # Save summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary = {
            'timestamp': timestamp,
            'stats': self.stats,
            'runtime_seconds': elapsed,
            'players_processed': [p['name'] for p in players[:self.stats['players_processed']]]
        }

        summary_file = f"pitch_collection_final_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\nSummary saved to: {summary_file}")

async def main():
    """Main entry point"""
    async with FinalPitchCollector() as collector:
        await collector.run_collection()

if __name__ == "__main__":
    asyncio.run(main())