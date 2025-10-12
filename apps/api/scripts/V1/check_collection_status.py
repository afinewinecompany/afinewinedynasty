"""
Check the status of MiLB data collection in the database.
Provides statistics on collected data by season and level.
"""

import asyncio
import asyncpg
from datetime import datetime
from pathlib import Path
import sys
import json
from typing import Dict, List
from tabulate import tabulate

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Make sure we're loading the env from the right place
import os
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings


class CollectionStatusChecker:
    """Check and report on MiLB data collection status."""

    def __init__(self):
        self.db_pool = None
        self.checkpoint_file = Path(__file__).parent / 'collection_checkpoint.json'

    async def init_db(self):
        """Initialize database connection."""
        try:
            db_url = str(settings.SQLALCHEMY_DATABASE_URI)
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            self.db_pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=5,
                command_timeout=60
            )
        except Exception as e:
            print(f"Failed to initialize database: {e}")
            raise

    async def close_db(self):
        """Close database connection."""
        if self.db_pool:
            await self.db_pool.close()

    def load_checkpoint(self) -> Dict:
        """Load checkpoint data if it exists."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading checkpoint: {e}")
        return {}

    async def get_overall_stats(self) -> Dict:
        """Get overall collection statistics."""
        async with self.db_pool.acquire() as conn:
            stats = {}

            # Total game logs
            stats['total_logs'] = await conn.fetchval(
                "SELECT COUNT(*) FROM milb_game_logs"
            )

            # Total unique players
            stats['unique_players'] = await conn.fetchval(
                "SELECT COUNT(DISTINCT mlb_player_id) FROM milb_game_logs"
            )

            # Total unique games
            stats['unique_games'] = await conn.fetchval(
                "SELECT COUNT(DISTINCT game_pk) FROM milb_game_logs"
            )

            # Date range
            date_range = await conn.fetchrow(
                """
                SELECT
                    MIN(game_date) as earliest,
                    MAX(game_date) as latest
                FROM milb_game_logs
                WHERE game_date IS NOT NULL
                """
            )
            stats['earliest_game'] = date_range['earliest']
            stats['latest_game'] = date_range['latest']

            # Logs with hitting stats
            stats['hitting_logs'] = await conn.fetchval(
                "SELECT COUNT(*) FROM milb_game_logs WHERE at_bats > 0"
            )

            # Logs with pitching stats
            stats['pitching_logs'] = await conn.fetchval(
                "SELECT COUNT(*) FROM milb_game_logs WHERE innings_pitched > 0"
            )

            return stats

    async def get_season_breakdown(self) -> List[Dict]:
        """Get breakdown by season."""
        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    season,
                    COUNT(*) as total_logs,
                    COUNT(DISTINCT mlb_player_id) as unique_players,
                    COUNT(DISTINCT game_pk) as unique_games,
                    COUNT(CASE WHEN at_bats > 0 THEN 1 END) as hitting_logs,
                    COUNT(CASE WHEN innings_pitched > 0 THEN 1 END) as pitching_logs,
                    MIN(game_date) as season_start,
                    MAX(game_date) as season_end
                FROM milb_game_logs
                GROUP BY season
                ORDER BY season DESC
                """
            )
            return [dict(row) for row in results]

    async def get_team_breakdown(self, season: int = None) -> List[Dict]:
        """Get breakdown by team."""
        query = """
            SELECT
                team_id,
                season,
                COUNT(*) as total_logs,
                COUNT(DISTINCT mlb_player_id) as unique_players
            FROM milb_game_logs
        """

        if season:
            query += f" WHERE season = {season}"

        query += """
            GROUP BY team_id, season
            ORDER BY season DESC, total_logs DESC
            LIMIT 50
        """

        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(query)
            return [dict(row) for row in results]

    async def get_prospect_stats(self, limit: int = 20) -> List[Dict]:
        """Get top prospects by game logs."""
        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(
                """
                SELECT
                    p.name,
                    p.position,
                    p.organization,
                    p.level,
                    COUNT(DISTINCT gl.game_pk) as games_played,
                    SUM(gl.at_bats) as total_at_bats,
                    SUM(gl.hits) as total_hits,
                    SUM(gl.home_runs) as total_home_runs,
                    SUM(gl.innings_pitched) as total_innings,
                    MIN(gl.season) as first_season,
                    MAX(gl.season) as last_season
                FROM milb_game_logs gl
                JOIN prospects p ON gl.prospect_id = p.id
                GROUP BY p.id, p.name, p.position, p.organization, p.level
                ORDER BY games_played DESC
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in results]

    async def check_data_quality(self) -> Dict:
        """Check data quality metrics."""
        async with self.db_pool.acquire() as conn:
            quality = {}

            # Logs with missing dates
            quality['missing_dates'] = await conn.fetchval(
                "SELECT COUNT(*) FROM milb_game_logs WHERE game_date IS NULL"
            )

            # Logs with missing team info
            quality['missing_teams'] = await conn.fetchval(
                "SELECT COUNT(*) FROM milb_game_logs WHERE team_id IS NULL"
            )

            # Duplicate checks
            quality['duplicate_games'] = await conn.fetchval(
                """
                SELECT COUNT(*) FROM (
                    SELECT mlb_player_id, game_pk, season, COUNT(*)
                    FROM milb_game_logs
                    GROUP BY mlb_player_id, game_pk, season
                    HAVING COUNT(*) > 1
                ) dupes
                """
            )

            # Players without prospect records
            quality['orphaned_players'] = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT mlb_player_id)
                FROM milb_game_logs
                WHERE prospect_id IS NULL
                """
            )

            return quality

    def print_report(self, overall_stats, season_breakdown, quality_metrics, checkpoint_data):
        """Print formatted status report."""
        print("\n" + "=" * 80)
        print("MiLB DATA COLLECTION STATUS REPORT")
        print("=" * 80)

        # Overall Statistics
        print("\nOVERALL STATISTICS")
        print("-" * 40)
        print(f"Total Game Logs:     {overall_stats['total_logs']:,}")
        print(f"Unique Players:      {overall_stats['unique_players']:,}")
        print(f"Unique Games:        {overall_stats['unique_games']:,}")
        print(f"Hitting Logs:        {overall_stats['hitting_logs']:,}")
        print(f"Pitching Logs:       {overall_stats['pitching_logs']:,}")

        if overall_stats['earliest_game'] and overall_stats['latest_game']:
            print(f"Date Range:          {overall_stats['earliest_game']} to {overall_stats['latest_game']}")

        # Season Breakdown
        print("\nSEASON BREAKDOWN")
        print("-" * 40)

        if season_breakdown:
            headers = ['Season', 'Total Logs', 'Players', 'Games', 'Hitting', 'Pitching']
            table_data = [
                [
                    row['season'],
                    f"{row['total_logs']:,}",
                    f"{row['unique_players']:,}",
                    f"{row['unique_games']:,}",
                    f"{row['hitting_logs']:,}",
                    f"{row['pitching_logs']:,}"
                ]
                for row in season_breakdown
            ]
            from tabulate import tabulate as tab
            print(tab(table_data, headers=headers, tablefmt='grid'))
        else:
            print("No season data found")

        # Checkpoint Status
        print("\nCHECKPOINT STATUS")
        print("-" * 40)

        if checkpoint_data:
            completed_seasons = checkpoint_data.get('completed_seasons', [])
            completed_teams = checkpoint_data.get('completed_teams', {})
            processed_players = checkpoint_data.get('processed_players', [])

            print(f"Completed Seasons:   {', '.join(map(str, completed_seasons)) if completed_seasons else 'None'}")
            print(f"Teams Processed:     {sum(len(teams) for teams in completed_teams.values())}")
            print(f"Players Processed:   {len(processed_players)}")

            # Show incomplete seasons
            target_seasons = [2021, 2022, 2023, 2024, 2025]
            incomplete = [s for s in target_seasons if s not in completed_seasons]
            if incomplete:
                print(f"Incomplete Seasons:  {', '.join(map(str, incomplete))}")
        else:
            print("No checkpoint file found")

        # Data Quality
        print("\nDATA QUALITY METRICS")
        print("-" * 40)
        print(f"Missing Dates:       {quality_metrics['missing_dates']:,}")
        print(f"Missing Teams:       {quality_metrics['missing_teams']:,}")
        print(f"Duplicate Games:     {quality_metrics['duplicate_games']:,}")
        print(f"Orphaned Players:    {quality_metrics['orphaned_players']:,}")

        # Collection Progress
        print("\nCOLLECTION PROGRESS")
        print("-" * 40)

        target_seasons = [2021, 2022, 2023, 2024, 2025]
        collected_seasons = [row['season'] for row in season_breakdown]

        for season in target_seasons:
            if season in collected_seasons:
                season_data = next(r for r in season_breakdown if r['season'] == season)
                status = f"[DONE] {season_data['total_logs']:,} logs"
            else:
                status = "[PENDING] Not started"
            print(f"  {season}: {status}")

        print("\n" + "=" * 80)


async def main():
    """Main execution function."""
    checker = CollectionStatusChecker()

    try:
        await checker.init_db()

        # Get all statistics
        overall_stats = await checker.get_overall_stats()
        season_breakdown = await checker.get_season_breakdown()
        quality_metrics = await checker.check_data_quality()
        checkpoint_data = checker.load_checkpoint()

        # Print report
        checker.print_report(overall_stats, season_breakdown, quality_metrics, checkpoint_data)

        # Optional: Get top prospects
        print("\nTOP PROSPECTS BY GAMES LOGGED")
        print("-" * 40)
        top_prospects = await checker.get_prospect_stats(10)

        if top_prospects:
            headers = ['Name', 'Pos', 'Org', 'Games', 'ABs', 'Hits', 'HRs']
            table_data = [
                [
                    row['name'][:20],
                    row['position'],
                    row['organization'][:15] if row['organization'] else 'N/A',
                    row['games_played'],
                    row['total_at_bats'] or 0,
                    row['total_hits'] or 0,
                    row['total_home_runs'] or 0
                ]
                for row in top_prospects
            ]
            from tabulate import tabulate as tab
            print(tab(table_data, headers=headers, tablefmt='simple'))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await checker.close_db()


if __name__ == "__main__":
    # Install tabulate if not present
    try:
        import tabulate
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'tabulate'])
        import tabulate

    asyncio.run(main())