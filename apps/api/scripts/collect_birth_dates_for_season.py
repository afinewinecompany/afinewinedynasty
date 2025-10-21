#!/usr/bin/env python3
"""
Collect Birth Dates for All MiLB Players by Season
===================================================
Updates prospects table with birth dates from MLB Stats API.
Can run concurrently for different seasons.

Usage:
    python collect_birth_dates_for_season.py --season 2024
    python collect_birth_dates_for_season.py --season 2025
"""

import asyncio
import asyncpg
import aiohttp
import os
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Set
from dotenv import load_dotenv

load_dotenv()

class BirthDateCollector:
    """Collects birth dates for MiLB players from MLB Stats API."""

    def __init__(self, season: int):
        self.season = season
        self.conn = None
        self.stats = {
            'total_players': 0,
            'in_prospects_table': 0,
            'already_have_birth_date': 0,
            'not_in_prospects': 0,
            'api_calls_made': 0,
            'successful': 0,
            'failed': 0,
            'start_time': datetime.now()
        }
        self.rate_limit_delay = 0.15  # 150ms between requests (6-7 req/sec)

    async def connect_db(self):
        """Connect to database."""
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
        self.conn = await asyncpg.connect(DATABASE_URL)
        print(f"[{self.season}] Connected to database")

    async def disconnect_db(self):
        """Disconnect from database."""
        if self.conn:
            await self.conn.close()
            print(f"[{self.season}] Disconnected from database")

    async def get_players_for_season(self) -> List[int]:
        """Get all unique player IDs from game logs for specified season."""
        player_ids = await self.conn.fetch("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = $1
                AND mlb_player_id IS NOT NULL
            ORDER BY mlb_player_id
        """, self.season)

        ids = [row['mlb_player_id'] for row in player_ids]
        self.stats['total_players'] = len(ids)
        print(f"[{self.season}] Found {len(ids):,} unique players in game logs")
        return ids

    async def get_prospects_with_player_ids(self) -> Dict[int, int]:
        """Get mapping of mlb_player_id to prospect id, and which have birth dates."""
        prospects = await self.conn.fetch("""
            SELECT id, mlb_player_id::integer as mlb_player_id, birth_date
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
        """)

        player_to_prospect = {}
        already_have = set()

        for row in prospects:
            try:
                player_id = int(row['mlb_player_id'])
                player_to_prospect[player_id] = row['id']
                if row['birth_date'] is not None:
                    already_have.add(player_id)
            except (ValueError, TypeError):
                continue

        self.stats['in_prospects_table'] = len(player_to_prospect)
        self.stats['already_have_birth_date'] = len(already_have)

        print(f"[{self.season}] {len(player_to_prospect):,} players are in prospects table")
        print(f"[{self.season}] {len(already_have):,} already have birth dates")

        return player_to_prospect, already_have

    async def fetch_player_bio(self, session: aiohttp.ClientSession, player_id: int) -> Optional[Dict]:
        """Fetch player biographical data from MLB Stats API."""
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'people' in data and len(data['people']) > 0:
                        return data['people'][0]
                elif response.status ==404:
                    # Player not found - normal for some IDs
                    return None
                else:
                    print(f"[{self.season}][WARN] API status {response.status} for player {player_id}")
                    return None
        except asyncio.TimeoutError:
            print(f"[{self.season}][WARN] Timeout for player {player_id}")
            return None
        except Exception as e:
            print(f"[{self.season}][ERROR] Failed to fetch player {player_id}: {e}")
            return None

        return None

    async def update_prospect_birth_date(self, prospect_id: int, player_id: int, bio_data: Dict) -> bool:
        """Update prospect record with birth date and other bio info."""
        try:
            await self.conn.execute("""
                UPDATE prospects
                SET
                    birth_date = $1,
                    birth_city = $2,
                    birth_country = $3,
                    height_inches = CASE
                        WHEN $4 IS NOT NULL THEN
                            CAST(SPLIT_PART($4, '''', 1) AS INTEGER) * 12 +
                            CAST(SPLIT_PART(SPLIT_PART($4, '''', 2), '"', 1) AS INTEGER)
                        ELSE height_inches
                    END,
                    weight_lbs = $5,
                    draft_year = $6,
                    mlb_debut_date = $7,
                    updated_at = NOW()
                WHERE id = $8
            """,
                bio_data.get('birthDate'),
                bio_data.get('birthCity'),
                bio_data.get('birthCountry'),
                bio_data.get('height'),  # Format: "6' 2\""
                bio_data.get('weight'),
                bio_data.get('draftYear'),
                bio_data.get('mlbDebutDate'),
                prospect_id
            )
            return True
        except Exception as e:
            print(f"[{self.season}][ERROR] Failed to update prospect {prospect_id} (player {player_id}): {e}")
            return False

    async def collect_birth_dates(self):
        """Main collection process."""
        print("="*80)
        print(f"BIRTH DATE COLLECTION - Season {self.season}")
        print("="*80)

        # Get players and prospects
        all_players = await self.get_players_for_season()
        player_to_prospect, already_have = await self.get_prospects_with_player_ids()

        # Filter to only players in prospects table who don't have birth dates
        players_to_fetch = [
            pid for pid in all_players
            if pid in player_to_prospect and pid not in already_have
        ]

        self.stats['not_in_prospects'] = sum(1 for pid in all_players if pid not in player_to_prospect)

        print(f"[{self.season}] Need to fetch: {len(players_to_fetch):,} players")
        print(f"[{self.season}] Not in prospects table: {self.stats['not_in_prospects']:,}")

        if len(players_to_fetch) == 0:
            print(f"[{self.season}] Nothing to do!")
            return

        print(f"\n[{self.season}] Starting API calls at {datetime.now().strftime('%H:%M:%S')}")
        print(f"[{self.season}] Rate: ~{1/self.rate_limit_delay:.1f} req/sec")

        # Create HTTP session
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        async with aiohttp.ClientSession(connector=connector) as session:
            for i, player_id in enumerate(players_to_fetch, 1):
                # Rate limiting
                await asyncio.sleep(self.rate_limit_delay)

                # Fetch bio data
                bio_data = await self.fetch_player_bio(session, player_id)
                self.stats['api_calls_made'] += 1

                if bio_data and 'birthDate' in bio_data:
                    # Update prospect record
                    prospect_id = player_to_prospect[player_id]
                    success = await self.update_prospect_birth_date(prospect_id, player_id, bio_data)
                    if success:
                        self.stats['successful'] += 1
                    else:
                        self.stats['failed'] += 1
                else:
                    self.stats['failed'] += 1

                # Progress updates every 50 players
                if i % 50 == 0 or i == len(players_to_fetch):
                    elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    eta_seconds = (len(players_to_fetch) - i) / rate if rate > 0 else 0
                    eta_minutes = eta_seconds / 60

                    print(f"[{self.season}] Progress: {i:,}/{len(players_to_fetch):,} "
                          f"({i/len(players_to_fetch)*100:.1f}%) | "
                          f"Success: {self.stats['successful']} | "
                          f"Failed: {self.stats['failed']} | "
                          f"ETA: {eta_minutes:.1f}min")

        print(f"\n[{self.season}] Finished at {datetime.now().strftime('%H:%M:%S')}")

    def print_summary(self):
        """Print collection summary."""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()

        print("\n" + "="*80)
        print(f"SUMMARY - Season {self.season}")
        print("="*80)
        print(f"Total players in game logs: {self.stats['total_players']:,}")
        print(f"In prospects table: {self.stats['in_prospects_table']:,}")
        print(f"Already had birth dates: {self.stats['already_have_birth_date']:,}")
        print(f"Not in prospects table: {self.stats['not_in_prospects']:,}")
        print(f"\nCollection Results:")
        print(f"  API calls made: {self.stats['api_calls_made']:,}")
        print(f"  Successful: {self.stats['successful']:,}")
        print(f"  Failed: {self.stats['failed']:,}")
        print(f"\nPerformance:")
        print(f"  Elapsed time: {elapsed/60:.1f} minutes")
        print(f"  Average rate: {self.stats['api_calls_made']/elapsed:.2f} req/sec")

        success_rate = self.stats['successful'] / self.stats['api_calls_made'] * 100 if self.stats['api_calls_made'] > 0 else 0
        print(f"  Success rate: {success_rate:.1f}%")
        print("="*80)

    async def run(self):
        """Execute full collection process."""
        try:
            await self.connect_db()
            await self.collect_birth_dates()
            self.print_summary()
        finally:
            await self.disconnect_db()


async def main():
    parser = argparse.ArgumentParser(description='Collect birth dates for MiLB players by season')
    parser.add_argument('--season', type=int, required=True, help='Season year (e.g., 2024 or 2025)')
    args = parser.parse_args()

    if args.season not in [2021, 2022, 2023, 2024, 2025]:
        print(f"[ERROR] Season must be between 2021-2025, got {args.season}")
        return

    collector = BirthDateCollector(args.season)
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
