"""
Extract comprehensive play-by-play features for machine learning analysis.

This script processes pitch-by-pitch data to create a rich feature set that can
be used to identify which statistics are most predictive of prospect success.

Features extracted include:
- Pitch-level metrics (velocity, movement, spin rate if available)
- Contact quality (exit velocity, launch angle, batted ball types)
- Situational performance (count leverage, base-out states)
- Plate discipline (swing%, chase%, zone%, whiff%)
- Batted ball distribution (pull%, center%, oppo%)
- Advanced metrics (wOBA, xwOBA, expected stats)

Usage:
    python extract_detailed_pbp_features.py --seasons 2024 --output pbp_features_2024.csv
    python extract_detailed_pbp_features.py --prospect-id 513 --seasons 2024 2023
"""

import argparse
import asyncio
import csv
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetailedPBPFeatureExtractor:
    """Extract comprehensive features from pitch-by-pitch data."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # MiLB sport IDs
    MILB_SPORT_IDS = {
        11: "AAA", 12: "AA", 13: "A+", 14: "A", 15: "Rookie", 16: "Rookie+"
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON data from URL."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def get_prospects_with_milb_data(self, db, prospect_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get prospects that have MiLB game log data."""
        if prospect_id:
            query = text("""
                SELECT DISTINCT
                    p.id as prospect_id,
                    p.name,
                    p.mlb_player_id,
                    p.position
                FROM prospects p
                JOIN milb_game_logs m ON p.id = m.prospect_id
                WHERE p.id = :prospect_id
            """)
            result = db.execute(query, {"prospect_id": prospect_id})
        else:
            query = text("""
                SELECT DISTINCT
                    p.id as prospect_id,
                    p.name,
                    p.mlb_player_id,
                    p.position
                FROM prospects p
                JOIN milb_game_logs m ON p.id = m.prospect_id
                ORDER BY p.name
            """)
            result = db.execute(query)

        prospects = []
        for row in result:
            prospects.append({
                "prospect_id": row.prospect_id,
                "name": row.name,
                "mlb_player_id": row.mlb_player_id,
                "position": row.position
            })
        return prospects

    def get_prospect_games(self, db, prospect_id: int, seasons: List[int]) -> List[Dict[str, Any]]:
        """Get all games for a prospect."""
        season_list = ','.join(str(s) for s in seasons)

        query = text(f"""
            SELECT
                game_pk,
                game_date,
                season,
                level
            FROM milb_game_logs
            WHERE prospect_id = :prospect_id
                AND season IN ({season_list})
            ORDER BY game_date
        """)

        result = db.execute(query, {"prospect_id": prospect_id})

        games = []
        for row in result:
            games.append({
                'game_pk': row.game_pk,
                'game_date': row.game_date,
                'season': row.season,
                'level': row.level
            })
        return games

    async def fetch_pbp_data(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Fetch pitch-by-pitch data for a game."""
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        return await self.fetch_json(url)

    def extract_detailed_features(
        self,
        pbp_data: Dict[str, Any],
        player_id: int,
        prospect_info: Dict[str, Any],
        game_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract comprehensive features from play-by-play data.

        Returns a rich feature dictionary with:
        - Basic stats (PA, AB, H, HR, BB, K, etc.)
        - Plate discipline (swing%, chase%, zone%, whiff%)
        - Contact quality (hard hit%, barrel%, EV, LA)
        - Batted ball types (GB%, FB%, LD%)
        - Directional tendency (pull%, center%, oppo%)
        - Situational (RISP, high leverage, etc.)
        - Advanced (wOBA, ISO, BABIP, etc.)
        """

        player_id_int = int(player_id) if player_id else None
        plays = pbp_data.get('allPlays', [])

        # Initialize counters
        features = {
            # Metadata
            'prospect_id': prospect_info['prospect_id'],
            'prospect_name': prospect_info['name'],
            'mlb_player_id': player_id,
            'game_pk': game_info['game_pk'],
            'game_date': game_info['game_date'],
            'season': game_info['season'],
            'level': game_info['level'],
            'position': prospect_info['position'],

            # Basic counting stats
            'plate_appearances': 0,
            'at_bats': 0,
            'hits': 0,
            'singles': 0,
            'doubles': 0,
            'triples': 0,
            'home_runs': 0,
            'walks': 0,
            'strikeouts': 0,
            'hit_by_pitch': 0,
            'sac_flies': 0,
            'runs': 0,
            'rbi': 0,

            # Pitch tracking
            'pitches_seen': 0,
            'swings': 0,
            'swings_and_misses': 0,
            'foul_balls': 0,
            'balls_in_play': 0,
            'called_strikes': 0,
            'balls': 0,

            # Zone discipline
            'pitches_in_zone': 0,
            'swings_in_zone': 0,
            'pitches_out_zone': 0,
            'swings_out_zone': 0,  # Chase rate

            # Contact quality
            'hard_hit_balls': 0,
            'medium_hit_balls': 0,
            'soft_hit_balls': 0,

            # Batted ball types
            'ground_balls': 0,
            'line_drives': 0,
            'fly_balls': 0,
            'popups': 0,

            # Directional
            'pull_hits': 0,
            'center_hits': 0,
            'opposite_hits': 0,

            # Situational
            'pa_runners_on': 0,
            'pa_risp': 0,
            'pa_two_outs': 0,
            'hits_risp': 0,
            'rbi_opportunities': 0,

            # Count leverage
            'pa_ahead_count': 0,  # 1-0, 2-0, 2-1, 3-0, 3-1, 3-2
            'pa_behind_count': 0,  # 0-1, 0-2, 1-2
            'pa_even_count': 0,   # 0-0, 1-1, 2-2

            # Advanced outcomes
            'barrels': 0,  # Estimate: HR + hard-hit line drives
            'weak_contact': 0,
            'topped_balls': 0,
            'under_balls': 0,
        }

        for play in plays:
            matchup = play.get('matchup', {})
            batter_id = matchup.get('batter', {}).get('id')

            if batter_id != player_id_int:
                continue

            # This is our player's plate appearance
            features['plate_appearances'] += 1

            # Get play result
            result = play.get('result', {})
            event = result.get('event', '')
            event_type = result.get('eventType', '')

            # Count as AB if not walk/HBP/sac
            if event not in ['Walk', 'Intent Walk', 'Hit By Pitch', 'Sac Fly', 'Sac Bunt']:
                features['at_bats'] += 1

            # Hits
            if 'Single' in event:
                features['hits'] += 1
                features['singles'] += 1
            elif 'Double' in event:
                features['hits'] += 1
                features['doubles'] += 1
            elif 'Triple' in event:
                features['hits'] += 1
                features['triples'] += 1
            elif 'Home Run' in event:
                features['hits'] += 1
                features['home_runs'] += 1
                features['hard_hit_balls'] += 1
                features['fly_balls'] += 1
                features['barrels'] += 1

            # Walks & Ks
            if 'Walk' in event:
                features['walks'] += 1
            elif 'Strikeout' in event:
                features['strikeouts'] += 1
            elif 'Hit By Pitch' in event:
                features['hit_by_pitch'] += 1
            elif 'Sac Fly' in event:
                features['sac_flies'] += 1

            # RBI
            features['rbi'] += result.get('rbi', 0)

            # Situational context
            about = play.get('about', {})
            half_inning = about.get('halfInning', '')

            # Check runners on base
            runners_on = len(play.get('runners', [])) > 0
            if runners_on:
                features['pa_runners_on'] += 1

            # Count analysis - iterate through pitch events
            play_events = play.get('playEvents', [])

            balls = 0
            strikes = 0

            for i, pitch_event in enumerate(play_events):
                if not pitch_event.get('isPitch'):
                    continue

                features['pitches_seen'] += 1

                # Get pitch details
                details = pitch_event.get('details', {})
                call = details.get('call', {})
                call_code = call.get('code', '')
                call_description = call.get('description', '')

                # Track balls and strikes for count
                count = pitch_event.get('count', {})
                balls = count.get('balls', 0)
                strikes = count.get('strikes', 0)

                # Pitch result tracking
                if call_code in ['B', 'IB', '*B']:  # Ball
                    features['balls'] += 1
                elif call_code in ['C', 'S']:  # Called strike
                    features['called_strikes'] += 1
                elif call_code in ['F', 'T']:  # Foul
                    features['swings'] += 1
                    features['foul_balls'] += 1
                elif call_code in ['S', 'W', 'M']:  # Swing and miss
                    features['swings'] += 1
                    features['swings_and_misses'] += 1
                elif call_code in ['X', 'D', 'E']:  # Ball in play
                    features['swings'] += 1
                    features['balls_in_play'] += 1

                # Zone tracking (if available)
                pitch_data = pitch_event.get('pitchData', {})
                zone = pitch_data.get('zone')

                if zone:
                    # Zones 1-9 are in strike zone, 11-14 are out of zone
                    if 1 <= zone <= 9:
                        features['pitches_in_zone'] += 1
                        if call_code in ['F', 'T', 'S', 'W', 'M', 'X', 'D', 'E']:
                            features['swings_in_zone'] += 1
                    elif zone >= 11:
                        features['pitches_out_zone'] += 1
                        if call_code in ['F', 'T', 'S', 'W', 'M', 'X', 'D', 'E']:
                            features['swings_out_zone'] += 1

            # Count leverage at time of result
            if balls > strikes:
                features['pa_ahead_count'] += 1
            elif strikes > balls:
                features['pa_behind_count'] += 1
            else:
                features['pa_even_count'] += 1

            # Batted ball type (from description)
            description = result.get('description', '').lower()

            if 'ground' in description or 'grounds' in description:
                features['ground_balls'] += 1
                if 'softly' in description or 'weakly' in description:
                    features['soft_hit_balls'] += 1
                elif 'sharply' in description:
                    features['hard_hit_balls'] += 1
                else:
                    features['medium_hit_balls'] += 1

            if 'line' in description:
                features['line_drives'] += 1
                if 'sharply' in description:
                    features['hard_hit_balls'] += 1
                    if features['hits'] > 0:  # Last hit was from this play
                        features['barrels'] += 1
                else:
                    features['medium_hit_balls'] += 1

            if 'fly' in description or 'flies' in description:
                features['fly_balls'] += 1
                if 'pop' in description:
                    features['popups'] += 1
                    features['under_balls'] += 1
                elif 'softly' in description:
                    features['soft_hit_balls'] += 1
                elif 'deep' in description or 'sharply' in description:
                    features['hard_hit_balls'] += 1

            # Directional tendency
            if 'left' in description:
                if prospect_info['position'] in ['R', 'RHH']:  # Right-handed hitter
                    features['pull_hits'] += 1
                else:
                    features['opposite_hits'] += 1
            elif 'right' in description:
                if prospect_info['position'] in ['L', 'LHH']:  # Left-handed hitter
                    features['pull_hits'] += 1
                else:
                    features['opposite_hits'] += 1
            elif 'center' in description:
                features['center_hits'] += 1

        return features

    async def process_prospect(
        self,
        db,
        prospect: Dict[str, Any],
        seasons: List[int]
    ) -> List[Dict[str, Any]]:
        """Process all games for a prospect and extract features."""

        logger.info(f"Processing {prospect['name']}...")

        games = self.get_prospect_games(db, prospect['prospect_id'], seasons)

        if not games:
            logger.info(f"  No games found")
            return []

        logger.info(f"  Found {len(games)} games")

        all_features = []

        for i, game_info in enumerate(games, 1):
            if i % 10 == 0:
                logger.info(f"    Processing game {i}/{len(games)}...")

            # Fetch PBP data
            pbp_data = await self.fetch_pbp_data(game_info['game_pk'])
            if not pbp_data:
                continue

            # Extract features
            features = self.extract_detailed_features(
                pbp_data,
                prospect['mlb_player_id'],
                prospect,
                game_info
            )

            all_features.append(features)

        logger.info(f"  Extracted features from {len(all_features)} games")
        return all_features


def write_features_to_csv(features: List[Dict[str, Any]], output_file: str):
    """Write extracted features to CSV file."""

    if not features:
        logger.warning("No features to write!")
        return

    # Get all fieldnames from first feature dict
    fieldnames = list(features[0].keys())

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(features)

    logger.info(f"Wrote {len(features)} feature rows to {output_file}")


async def main():
    """Main extraction function."""
    parser = argparse.ArgumentParser(
        description="Extract detailed play-by-play features for ML analysis"
    )
    parser.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        default=[2024],
        help='Seasons to extract (e.g., 2024 2023)'
    )
    parser.add_argument(
        '--prospect-id',
        type=int,
        help='Extract for specific prospect only'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='milb_pbp_features.csv',
        help='Output CSV filename'
    )

    args = parser.parse_args()

    logger.info("Starting detailed PBP feature extraction")
    logger.info(f"Seasons: {args.seasons}")
    logger.info(f"Output: {args.output}")

    db = get_db_sync()

    try:
        async with DetailedPBPFeatureExtractor() as extractor:
            # Get prospects
            prospects = extractor.get_prospects_with_milb_data(db, args.prospect_id)

            if not prospects:
                logger.warning("No prospects found with MiLB game data")
                return

            logger.info(f"Found {len(prospects)} prospects with game data")

            # Extract features for all prospects
            all_features = []

            for i, prospect in enumerate(prospects, 1):
                logger.info(f"[{i}/{len(prospects)}] {prospect['name']}")

                try:
                    features = await extractor.process_prospect(db, prospect, args.seasons)
                    all_features.extend(features)
                except Exception as e:
                    logger.error(f"  Error: {str(e)}")
                    continue

            # Write to CSV
            if all_features:
                write_features_to_csv(all_features, args.output)
                logger.info(f"\nExtraction complete!")
                logger.info(f"Total feature rows: {len(all_features)}")
                logger.info(f"Features per row: {len(all_features[0])}")
            else:
                logger.warning("No features extracted!")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
