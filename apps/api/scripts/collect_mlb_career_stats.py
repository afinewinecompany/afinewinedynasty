"""
Collect MLB Career Stats for MiLB-to-MLB Projection Model

This script identifies all players in our MiLB database who have made it to MLB,
then collects their MLB career statistics. This creates the target variable for
our machine learning model that predicts MLB success from MiLB performance.

Strategy:
1. Query all unique MiLB players we have stats for
2. Check if each player has MLB game logs (sportId=1)
3. Collect their MLB career statistics
4. Store in mlb_stats table for ML training

This enables supervised learning:
- Features: MiLB performance stats (from milb_game_logs)
- Target: MLB performance stats (from mlb_stats)
- Goal: Predict which MiLB stats best translate to MLB success

Usage:
    python collect_mlb_career_stats.py --min-pa 50
    python collect_mlb_career_stats.py --seasons 2024 2023 2022
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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


class MLBCareerStatsCollector:
    """Collect MLB career stats for players who graduated from minors."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    def __init__(self, min_mlb_pa: int = 50):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.min_mlb_pa = min_mlb_pa
        self.stats_collected = 0
        self.players_with_mlb = 0
        self.players_checked = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from URL with rate limiting."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def get_milb_players_with_ids(self) -> List[Dict[str, Any]]:
        """Get all unique MiLB players we have stats for."""
        db = get_db_sync()

        result = db.execute(text("""
            SELECT DISTINCT
                mlb_player_id,
                prospect_id,
                MIN(season) as first_milb_season,
                MAX(season) as last_milb_season,
                COUNT(*) as milb_games
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id, prospect_id
            ORDER BY last_milb_season DESC
        """))

        players = []
        for row in result:
            players.append({
                'mlb_player_id': row[0],
                'prospect_id': row[1],
                'first_milb_season': row[2],
                'last_milb_season': row[3],
                'milb_games': row[4]
            })

        logger.info(f"Found {len(players)} unique MiLB players with MLB IDs")
        return players

    async def check_mlb_career(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Check if player has MLB stats and get debut info."""
        # Try to get MLB stats (sportId=1)
        url = f"{self.BASE_URL}/people/{player_id}/stats?stats=career&group=hitting&sportId=1"

        data = await self.fetch_json(url)
        if not data:
            return None

        stats_list = data.get('stats', [])
        if not stats_list:
            return None

        splits = stats_list[0].get('splits', [])
        if not splits:
            return None

        career_stats = splits[0].get('stat', {})

        # Check minimum PA threshold
        pa = career_stats.get('plateAppearances', 0)
        if pa < self.min_mlb_pa:
            return None

        # Get debut date from person endpoint
        person_url = f"{self.BASE_URL}/people/{player_id}"
        person_data = await self.fetch_json(person_url)

        debut_date = None
        if person_data:
            people = person_data.get('people', [])
            if people:
                debut_str = people[0].get('mlbDebutDate')
                if debut_str:
                    debut_date = datetime.strptime(debut_str, '%Y-%m-%d').date()

        return {
            'debut_date': debut_date,
            'career_stats': career_stats
        }

    async def get_mlb_season_stats(self, player_id: int, start_season: int, end_season: int) -> List[Dict[str, Any]]:
        """Get MLB stats by season for a player."""
        season_stats = []

        for season in range(start_season, end_season + 1):
            url = f"{self.BASE_URL}/people/{player_id}/stats?stats=season&season={season}&group=hitting&sportId=1"

            data = await self.fetch_json(url)
            if not data:
                continue

            stats_list = data.get('stats', [])
            if not stats_list:
                continue

            splits = stats_list[0].get('splits', [])
            if not splits:
                continue

            for split in splits:
                stat = split.get('stat', {})
                if stat.get('plateAppearances', 0) > 0:
                    season_stats.append({
                        'season': season,
                        'stats': stat
                    })

        return season_stats

    async def save_mlb_stats(self, prospect_id: int, player_id: int, mlb_data: Dict[str, Any], seasons: List[Dict[str, Any]]):
        """Save MLB career stats to database."""
        db = next(get_db_sync())

        career = mlb_data['career_stats']

        # Save career aggregated stats
        career_record = {
            'prospect_id': prospect_id,
            'season': 0,  # 0 indicates career totals
            'mlb_debut_date': mlb_data['debut_date'],
            'games_played': career.get('gamesPlayed', 0),
            'plate_appearances': career.get('plateAppearances', 0),
            'at_bats': career.get('atBats', 0),
            'runs': career.get('runs', 0),
            'hits': career.get('hits', 0),
            'doubles': career.get('doubles', 0),
            'triples': career.get('triples', 0),
            'home_runs': career.get('homeRuns', 0),
            'rbi': career.get('rbi', 0),
            'walks': career.get('baseOnBalls', 0),
            'strikeouts': career.get('strikeOuts', 0),
            'stolen_bases': career.get('stolenBases', 0),
            'caught_stealing': career.get('caughtStealing', 0),
            'batting_avg': float(career.get('avg', 0)) if career.get('avg') else None,
            'on_base_pct': float(career.get('obp', 0)) if career.get('obp') else None,
            'slugging_pct': float(career.get('slg', 0)) if career.get('slg') else None,
            'ops': float(career.get('ops', 0)) if career.get('ops') else None,
            'ops_plus': career.get('opsPlus'),
            'ground_balls': career.get('groundOuts', 0),
            'fly_balls': career.get('flyOuts', 0),
            'data_source': 'mlb_stats_api'
        }

        try:
            # Insert or update career stats
            db.execute(text("""
                INSERT INTO mlb_stats (
                    prospect_id, season, mlb_debut_date, games_played,
                    plate_appearances, at_bats, runs, hits, doubles, triples,
                    home_runs, rbi, walks, strikeouts, stolen_bases, caught_stealing,
                    batting_avg, on_base_pct, slugging_pct, ops, ops_plus,
                    ground_balls, fly_balls, data_source
                ) VALUES (
                    :prospect_id, :season, :mlb_debut_date, :games_played,
                    :plate_appearances, :at_bats, :runs, :hits, :doubles, :triples,
                    :home_runs, :rbi, :walks, :strikeouts, :stolen_bases, :caught_stealing,
                    :batting_avg, :on_base_pct, :slugging_pct, :ops, :ops_plus,
                    :ground_balls, :fly_balls, :data_source
                )
                ON CONFLICT (prospect_id, season)
                DO UPDATE SET
                    mlb_debut_date = EXCLUDED.mlb_debut_date,
                    games_played = EXCLUDED.games_played,
                    plate_appearances = EXCLUDED.plate_appearances,
                    at_bats = EXCLUDED.at_bats,
                    runs = EXCLUDED.runs,
                    hits = EXCLUDED.hits,
                    doubles = EXCLUDED.doubles,
                    triples = EXCLUDED.triples,
                    home_runs = EXCLUDED.home_runs,
                    rbi = EXCLUDED.rbi,
                    walks = EXCLUDED.walks,
                    strikeouts = EXCLUDED.strikeouts,
                    stolen_bases = EXCLUDED.stolen_bases,
                    caught_stealing = EXCLUDED.caught_stealing,
                    batting_avg = EXCLUDED.batting_avg,
                    on_base_pct = EXCLUDED.on_base_pct,
                    slugging_pct = EXCLUDED.slugging_pct,
                    ops = EXCLUDED.ops,
                    ops_plus = EXCLUDED.ops_plus,
                    ground_balls = EXCLUDED.ground_balls,
                    fly_balls = EXCLUDED.fly_balls,
                    updated_at = NOW()
            """), career_record)

            db.commit()
            self.stats_collected += 1

        except Exception as e:
            logger.error(f"Error saving MLB stats for prospect {prospect_id}: {str(e)}")
            db.rollback()

    async def process_player(self, player: Dict[str, Any]):
        """Process a single MiLB player to collect their MLB stats."""
        player_id = player['mlb_player_id']
        prospect_id = player['prospect_id']

        self.players_checked += 1

        # Check if player has MLB career
        mlb_data = await self.check_mlb_career(player_id)

        if not mlb_data:
            return

        self.players_with_mlb += 1

        # Get season-by-season stats
        current_year = datetime.now().year
        first_mlb_season = mlb_data['debut_date'].year if mlb_data['debut_date'] else player['last_milb_season'] + 1

        seasons = await self.get_mlb_season_stats(player_id, first_mlb_season, current_year)

        # Save to database
        await self.save_mlb_stats(prospect_id, player_id, mlb_data, seasons)

        career_pa = mlb_data['career_stats'].get('plateAppearances', 0)
        career_ops = mlb_data['career_stats'].get('ops', 0)

        logger.info(f"  [{self.players_checked}/{len(self.milb_players)}] Player {player_id}: {career_pa} PA, {career_ops} OPS in MLB")

    async def collect_all_mlb_stats(self):
        """Main collection loop."""
        logger.info("Starting MLB career stats collection...")
        logger.info(f"Minimum MLB PA threshold: {self.min_mlb_pa}")

        # Get all MiLB players
        self.milb_players = await self.get_milb_players_with_ids()

        if not self.milb_players:
            logger.info("No MiLB players found")
            return

        logger.info(f"\nProcessing {len(self.milb_players)} MiLB players...")

        # Process each player
        for player in self.milb_players:
            await self.process_player(player)

            # Progress update every 50 players
            if self.players_checked % 50 == 0:
                logger.info(f"\nProgress: {self.players_checked}/{len(self.milb_players)} players checked")
                logger.info(f"  Found {self.players_with_mlb} with MLB careers ({self.min_mlb_pa}+ PA)")
                logger.info(f"  Saved {self.stats_collected} MLB stat records\n")

        logger.info("\n" + "="*80)
        logger.info("MLB CAREER STATS COLLECTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Total MiLB players checked: {self.players_checked}")
        logger.info(f"Players with MLB careers: {self.players_with_mlb}")
        logger.info(f"MLB stat records saved: {self.stats_collected}")
        logger.info(f"Conversion rate: {(self.players_with_mlb/self.players_checked*100):.1f}%")


async def main():
    parser = argparse.ArgumentParser(description='Collect MLB career stats for MiLB players')
    parser.add_argument('--min-pa', type=int, default=50,
                       help='Minimum MLB plate appearances to include (default: 50)')

    args = parser.parse_args()

    async with MLBCareerStatsCollector(min_mlb_pa=args.min_pa) as collector:
        await collector.collect_all_mlb_stats()


if __name__ == "__main__":
    asyncio.run(main())
