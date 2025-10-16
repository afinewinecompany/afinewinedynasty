"""
Collect pitch-by-pitch data for BATTERS and PITCHERS for 2025 season.

This script collects detailed pitch-level data from MLB Stats API for all players
who played in 2025. Creates records in both milb_batter_pitches and milb_pitcher_pitches.

Run concurrently with other season scripts for faster collection.

Usage:
    python collect_pitch_data_2025.py --limit 100  # Test with 100 players
    python collect_pitch_data_2025.py              # Full collection
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import aiohttp
from sqlalchemy import text

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from app.db.database import get_db_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [2025] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SEASON = 2025

class PitchDataCollector2025:
    """Collect pitch-level data for 2025 season."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"
    MILB_SPORT_IDS = {
        11: "AAA", 12: "AA", 13: "A+", 14: "A",
        15: "Rookie", 16: "Rookie+", 21: "Complex"
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.3
        self.games_processed = 0
        self.pitches_collected = 0
        self.errors = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "A Fine Wine Dynasty Bot 1.0 (Research/Educational)",
                "Accept": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON with rate limiting."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            self.errors += 1
            return None

    def get_players_for_season(self, db, limit: Optional[int] = None) -> List[Dict]:
        """Get prospects with MLB IDs who played in 2025."""
        query = text("""
            SELECT DISTINCT
                CAST(p.mlb_player_id AS INTEGER) as mlb_player_id,
                p.name,
                p.position,
                p.organization,
                COUNT(g.game_pk) as game_count
            FROM prospects p
            INNER JOIN milb_game_logs g ON g.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE g.season = :season
            AND p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            GROUP BY p.mlb_player_id, p.name, p.position, p.organization
            HAVING COUNT(g.game_pk) > 10
            ORDER BY game_count DESC
            LIMIT :limit
        """)

        result = db.execute(query, {"season": SEASON, "limit": limit or 10000})

        players = []
        for row in result:
            players.append({
                "mlb_player_id": row.mlb_player_id,
                                "name": row.name or f"Player {row.mlb_player_id}",
                                "position": row.position,
                                "organization": row.organization,
                "game_count": row.game_count
            })

        return players

    async def find_player_games(self, player_id: int) -> List[Dict]:
        """Find all games for player in 2025."""
        all_games = {}

        for sport_id, level_name in self.MILB_SPORT_IDS.items():
            url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={SEASON}&group=hitting,pitching&sportId={sport_id}"
            data = await self.fetch_json(url)

            if not data:
                continue

            try:
                stats = data.get('stats', [])
                for stat_group in stats:
                    splits = stat_group.get('splits', [])
                    for split in splits:
                        game = split.get('game', {})
                        game_pk = game.get('gamePk')
                        game_date = split.get('date')

                        if game_pk and game_date:
                            all_games[game_pk] = {
                                'game_pk': game_pk,
                                'game_date': game_date,
                                'level': level_name
                            }
            except Exception as e:
                logger.error(f"Error parsing games for sport {sport_id}: {e}")
                continue

        return list(all_games.values())

    async def fetch_game_pbp(self, game_pk: int) -> Optional[Dict]:
        """Fetch game play-by-play data.

        For MiLB games, playByPlay endpoint is more reliable than feed/live.
        """
        # Try playByPlay first (works for MiLB)
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        data = await self.fetch_json(url)

        if data:
            return data

        # Fallback to feed/live
        url = f"{self.BASE_URL}/game/{game_pk}/feed/live"
        return await self.fetch_json(url)

    def extract_pitch_data(
        self,
        play_event: Dict,
        matchup: Dict,
        about: Dict,
        at_bat_index: int,
        pitch_number: int,
        game_pk: int,
        game_date: str,
        level: str,
        is_final_pitch: bool = False,
        pa_result: str = None,
        pa_result_desc: str = None,
        batted_ball_data: Dict = None
    ) -> Dict:
        """Extract pitch-level data from play event."""

        pitch_data = play_event.get('pitchData', {})
        details = play_event.get('details', {})
        count = play_event.get('count', {})

        # Basic pitch info
        pitch_type = details.get('type', {}).get('code')
        pitch_type_desc = details.get('type', {}).get('description')
        pitch_call = details.get('description')

        # Velocity & movement
        start_speed = pitch_data.get('startSpeed')
        end_speed = pitch_data.get('endSpeed')
        pfx_x = pitch_data.get('breaks', {}).get('breakHorizontal')
        pfx_z = pitch_data.get('breaks', {}).get('breakVertical')

        # Release point
        release_pos_x = pitch_data.get('coordinates', {}).get('x')
        release_pos_y = pitch_data.get('coordinates', {}).get('y')
        release_pos_z = pitch_data.get('coordinates', {}).get('z')
        release_extension = pitch_data.get('extension')

        # Spin
        spin_rate = pitch_data.get('breaks', {}).get('spinRate')
        spin_direction = pitch_data.get('breaks', {}).get('spinDirection')

        # Location
        plate_x = pitch_data.get('coordinates', {}).get('pX')
        plate_z = pitch_data.get('coordinates', {}).get('pZ')
        zone = pitch_data.get('zone')

        # Result
        is_strike = pitch_call in [
            'Called Strike', 'Swinging Strike', 'Foul', 'Foul Tip',
            'Swinging Strike (Blocked)', 'Foul Bunt'
        ]

        # Swing/Contact
        swing = 'Swing' in pitch_call if pitch_call else False
        contact = pitch_call in ['Foul', 'Foul Tip', 'In play, out(s)', 'In play, no out', 'In play, run(s)'] if pitch_call else False
        swing_and_miss = pitch_call == 'Swinging Strike' if pitch_call else False
        foul = 'Foul' in pitch_call if pitch_call else False

        return {
            'mlb_batter_id': matchup.get('batter', {}).get('id'),
            'mlb_pitcher_id': matchup.get('pitcher', {}).get('id'),
            'game_pk': game_pk,
            'game_date': datetime.strptime(game_date, '%Y-%m-%d').date(),
            'season': SEASON,
            'level': level,
            'at_bat_index': at_bat_index,
            'pitch_number': pitch_number,
            'inning': about.get('inning'),
            'half_inning': about.get('halfInning'),
            'pitch_type': pitch_type,
            'pitch_type_description': pitch_type_desc,
            'start_speed': start_speed,
            'end_speed': end_speed,
            'pfx_x': pfx_x,
            'pfx_z': pfx_z,
            'release_pos_x': release_pos_x,
            'release_pos_y': release_pos_y,
            'release_pos_z': release_pos_z,
            'release_extension': release_extension,
            'spin_rate': spin_rate,
            'spin_direction': spin_direction,
            'plate_x': plate_x,
            'plate_z': plate_z,
            'zone': zone,
            'pitch_call': pitch_call,
            'pitch_result': details.get('call', {}).get('description'),
            'is_strike': is_strike,
            'balls': count.get('balls'),
            'strikes': count.get('strikes'),
            'outs': count.get('outs'),
            'swing': swing,
            'contact': contact,
            'swing_and_miss': swing_and_miss,
            'foul': foul,
            'is_final_pitch': is_final_pitch,
            'pa_result': pa_result,
            'pa_result_description': pa_result_desc,
            'launch_speed': batted_ball_data.get('launch_speed') if batted_ball_data else None,
            'launch_angle': batted_ball_data.get('launch_angle') if batted_ball_data else None,
            'total_distance': batted_ball_data.get('total_distance') if batted_ball_data else None,
            'trajectory': batted_ball_data.get('trajectory') if batted_ball_data else None,
            'hardness': batted_ball_data.get('hardness') if batted_ball_data else None,
            'hit_location': batted_ball_data.get('location') if batted_ball_data else None,
            'coord_x': batted_ball_data.get('coord_x') if batted_ball_data else None,
            'coord_y': batted_ball_data.get('coord_y') if batted_ball_data else None
        }

    def save_pitch_data(self, db, pitch_data: Dict, player_id: int, is_pitcher: bool):
        """Save pitch data to appropriate table."""
        table = 'milb_pitcher_pitches' if is_pitcher else 'milb_batter_pitches'
        id_field = 'mlb_pitcher_id' if is_pitcher else 'mlb_batter_id'

        # Check if already exists
        check_query = text(f"""
            SELECT id FROM {table}
            WHERE {id_field} = :player_id
            AND game_pk = :game_pk
            AND at_bat_index = :at_bat_index
            AND pitch_number = :pitch_number
        """)

        existing = db.execute(check_query, {
            'player_id': player_id,
            'game_pk': pitch_data['game_pk'],
            'at_bat_index': pitch_data['at_bat_index'],
            'pitch_number': pitch_data['pitch_number']
        }).fetchone()

        if existing:
            return False

        # Build insert query
        columns = [k for k in pitch_data.keys() if pitch_data[k] is not None]
        placeholders = [f":{col}" for col in columns]

        insert_query = text(f"""
            INSERT INTO {table} ({', '.join(columns)}, created_at)
            VALUES ({', '.join(placeholders)}, NOW())
        """)

        try:
            db.execute(insert_query, pitch_data)
            return True
        except Exception as e:
            logger.error(f"Error inserting pitch: {e}")
            return False

    async def process_game(self, db, game_info: Dict, player_id: int) -> int:
        """Process a single game and extract pitch data."""
        game_pk = game_info['game_pk']
        game_date = game_info['game_date']
        level = game_info['level']

        # Fetch game data
        pbp_data = await self.fetch_game_pbp(game_pk)
        if not pbp_data:
            return 0

        # Get plays
        if 'liveData' in pbp_data:
            all_plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
        else:
            all_plays = pbp_data.get('allPlays', [])

        if not all_plays:
            return 0

        pitches_saved = 0

        try:
            for play in all_plays:
                matchup = play.get('matchup', {})
                batter_id = matchup.get('batter', {}).get('id')
                pitcher_id = matchup.get('pitcher', {}).get('id')

                # Only process if our player is involved
                if batter_id != player_id and pitcher_id != player_id:
                    continue

                about = play.get('about', {})
                at_bat_index = play.get('atBatIndex', 0)
                play_events = play.get('playEvents', [])
                result = play.get('result', {})

                # Get batted ball data if available
                batted_ball_data = None
                for event in play_events:
                    hit_data = event.get('hitData', {})
                    if hit_data:
                        batted_ball_data = {
                            'launch_speed': hit_data.get('launchSpeed'),
                            'launch_angle': hit_data.get('launchAngle'),
                            'total_distance': hit_data.get('totalDistance'),
                            'trajectory': hit_data.get('trajectory'),
                            'hardness': hit_data.get('hardness'),
                            'location': hit_data.get('location'),
                            'coord_x': hit_data.get('coordinates', {}).get('coordX'),
                            'coord_y': hit_data.get('coordinates', {}).get('coordY')
                        }
                        break

                # Process each pitch in the at-bat
                pitch_events = [e for e in play_events if e.get('isPitch')]

                for pitch_num, pitch_event in enumerate(pitch_events, 1):
                    is_final = (pitch_num == len(pitch_events))

                    pitch_data = self.extract_pitch_data(
                        pitch_event,
                        matchup,
                        about,
                        at_bat_index,
                        pitch_num,
                        game_pk,
                        game_date,
                        level,
                        is_final,
                        result.get('event') if is_final else None,
                        result.get('description') if is_final else None,
                        batted_ball_data if is_final else None
                    )

                    # Save for batter if player is batter
                    if batter_id == player_id:
                        if self.save_pitch_data(db, pitch_data, player_id, False):
                            pitches_saved += 1

                    # Save for pitcher if player is pitcher
                    if pitcher_id == player_id:
                        if self.save_pitch_data(db, pitch_data, player_id, True):
                            pitches_saved += 1

            if pitches_saved > 0:
                db.commit()
                self.pitches_collected += pitches_saved

        except Exception as e:
            logger.error(f"Error processing game {game_pk}: {e}")
            db.rollback()

        return pitches_saved

    async def collect_player_data(self, db, player: Dict) -> int:
        """Collect all pitch data for a player."""
        player_id = player['mlb_player_id']
        name = player['name']

        logger.info(f"  Processing {name} (ID: {player_id})")

        # Find games
        games = await self.find_player_games(player_id)
        if not games:
            logger.info(f"    No games found")
            return 0

        logger.info(f"    Found {len(games)} games")

        total_pitches = 0
        for i, game_info in enumerate(games, 1):
            if i % 20 == 0:
                logger.info(f"      Progress: {i}/{len(games)} games")

            pitches = await self.process_game(db, game_info, player_id)
            total_pitches += pitches

            if pitches > 0:
                self.games_processed += 1

        logger.info(f"    Collected {total_pitches} pitches")
        return total_pitches


async def main():
    parser = argparse.ArgumentParser(description=f"Collect pitch data for {SEASON}")
    parser.add_argument('--limit', type=int, help='Limit number of players')
    args = parser.parse_args()

    logger.info("="*80)
    logger.info(f"PITCH-BY-PITCH DATA COLLECTION - {SEASON} SEASON")
    logger.info("="*80)

    db = get_db_sync()

    try:
        async with PitchDataCollector2025() as collector:
            # Get players
            players = collector.get_players_for_season(db, args.limit)
            logger.info(f"Found {len(players)} players for {SEASON}")
            logger.info("")

            if not players:
                logger.warning("No players found")
                return

            start_time = time.time()

            for i, player in enumerate(players, 1):
                logger.info(f"[{i}/{len(players)}] {player['name']} ({player['organization']})")

                try:
                    await collector.collect_player_data(db, player)
                except Exception as e:
                    logger.error(f"  ERROR: {e}")
                    collector.errors += 1

                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    logger.info("")
                    logger.info(f"Progress: {i}/{len(players)} players")
                    logger.info(f"Pitches collected: {collector.pitches_collected:,}")
                    logger.info(f"Games processed: {collector.games_processed}")
                    logger.info(f"Errors: {collector.errors}")
                    logger.info("")

            # Final summary
            elapsed = time.time() - start_time
            logger.info("")
            logger.info("="*80)
            logger.info("COLLECTION COMPLETE - 2025")
            logger.info("="*80)
            logger.info(f"Total pitches collected: {collector.pitches_collected:,}")
            logger.info(f"Games processed: {collector.games_processed}")
            logger.info(f"Errors: {collector.errors}")
            logger.info(f"Time: {elapsed:.1f}s")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
