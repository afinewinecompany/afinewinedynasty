"""
Collect MLB Career Stats for MiLB-to-MLB Projection Model (Fixed Version)

Collects MLB career statistics for all players in our MiLB database who made it to MLB.
This enables supervised learning to predict MLB success from MiLB performance.

Usage:
    python collect_mlb_career_stats_fixed.py --min-pa 50
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import text

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

    async def get_milb_players(self) -> List[Dict[str, Any]]:
        """Get all unique MiLB players we have stats for."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
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
        """Check if player has MLB stats and get career data."""
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
        pa = career_stats.get('plateAppearances', 0)

        if pa < self.min_mlb_pa:
            return None

        # Get debut date
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

    async def save_mlb_stats(self, prospect_id: int, mlb_data: Dict[str, Any]):
        """Save MLB career stats to database."""
        career = mlb_data['career_stats']

        record = {
            'prospect_id': prospect_id,
            'season': 0,  # 0 = career totals
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
            async with engine.begin() as conn:
                await conn.execute(text("""
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
                        batting_avg = EXCLUDED.batting_avg,
                        on_base_pct = EXCLUDED.on_base_pct,
                        slugging_pct = EXCLUDED.slugging_pct,
                        ops = EXCLUDED.ops,
                        updated_at = NOW()
                """), record)

            self.stats_collected += 1

        except Exception as e:
            logger.error(f"Error saving MLB stats for prospect {prospect_id}: {str(e)}")

    async def process_player(self, player: Dict[str, Any]):
        """Process a single MiLB player to collect their MLB stats."""
        player_id = player['mlb_player_id']
        prospect_id = player['prospect_id']

        self.players_checked += 1

        mlb_data = await self.check_mlb_career(player_id)
        if not mlb_data:
            return

        self.players_with_mlb += 1

        await self.save_mlb_stats(prospect_id, mlb_data)

        career_pa = mlb_data['career_stats'].get('plateAppearances', 0)
        career_ops = mlb_data['career_stats'].get('ops', 0)

        logger.info(f"  [{self.players_checked}/{len(self.milb_players)}] Player {player_id}: {career_pa} PA, {career_ops} OPS in MLB")

        if self.players_checked % 10 == 0:
            logger.info(f"\nProgress: {self.players_checked}/{len(self.milb_players)} checked, {self.players_with_mlb} with MLB careers\n")

    async def collect_all_mlb_stats(self):
        """Main collection loop."""
        logger.info("Starting MLB career stats collection...")
        logger.info(f"Minimum MLB PA threshold: {self.min_mlb_pa}")

        self.milb_players = await self.get_milb_players()

        if not self.milb_players:
            logger.info("No MiLB players found")
            return

        logger.info(f"\nProcessing {len(self.milb_players)} MiLB players...\n")

        for player in self.milb_players:
            await self.process_player(player)

        logger.info("\n" + "="*80)
        logger.info("MLB CAREER STATS COLLECTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Total MiLB players checked: {self.players_checked}")
        logger.info(f"Players with MLB careers: {self.players_with_mlb}")
        logger.info(f"MLB stat records saved: {self.stats_collected}")
        logger.info(f"Conversion rate: {(self.players_with_mlb/max(self.players_checked,1)*100):.1f}%")


async def main():
    parser = argparse.ArgumentParser(description='Collect MLB career stats for MiLB players')
    parser.add_argument('--min-pa', type=int, default=50,
                       help='Minimum MLB plate appearances to include (default: 50)')

    args = parser.parse_args()

    async with MLBCareerStatsCollector(min_mlb_pa=args.min_pa) as collector:
        await collector.collect_all_mlb_stats()


if __name__ == "__main__":
    asyncio.run(main())
