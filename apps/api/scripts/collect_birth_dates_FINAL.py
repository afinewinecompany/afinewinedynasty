#!/usr/bin/env python3
"""
Collect Birth Dates - FINAL WORKING VERSION
============================================
Properly converts date strings to Python date objects.
"""

import asyncio
import asyncpg
import aiohttp
import os
import argparse
from datetime import datetime, date
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class BirthDateCollector:
    def __init__(self, season: int):
        self.season = season
        self.conn = None
        self.stats = {
            'total_players': 0,
            'api_calls_made': 0,
            'successful': 0,
            'failed': 0,
            'start_time': datetime.now()
        }
        self.rate_limit_delay = 0.15

    async def connect_db(self):
        DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
        self.conn = await asyncpg.connect(DATABASE_URL)
        print(f"[{self.season}] Connected")

    async def disconnect_db(self):
        if self.conn:
            await self.conn.close()

    async def get_players_for_season(self) -> List[int]:
        player_ids = await self.conn.fetch("""
            SELECT DISTINCT mlb_player_id
            FROM milb_game_logs
            WHERE season = $1 AND mlb_player_id IS NOT NULL
            ORDER BY mlb_player_id
        """, self.season)
        return [row['mlb_player_id'] for row in player_ids]

    async def get_prospects_with_player_ids(self):
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
            except:
                continue
        return player_to_prospect, already_have

    async def fetch_player_bio(self, session: aiohttp.ClientSession, player_id: int) -> Optional[Dict]:
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'people' in data and len(data['people']) > 0:
                        return data['people'][0]
        except:
            pass
        return None

    def parse_height(self, height_str: Optional[str]) -> Optional[int]:
        if not height_str:
            return None
        try:
            parts = height_str.replace('"', '').split("'")
            if len(parts) == 2:
                feet = int(parts[0].strip())
                inches = int(parts[1].strip()) if parts[1].strip() else 0
                return feet * 12 + inches
        except:
            pass
        return None

    def parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Convert '1994-11-09' string to Python date object"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None

    async def update_prospect(self, prospect_id: int, bio_data: Dict) -> bool:
        try:
            # Convert all the data BEFORE passing to SQL
            birth_date = self.parse_date(bio_data.get('birthDate'))
            height_inches = self.parse_height(bio_data.get('height'))
            mlb_debut_date = self.parse_date(bio_data.get('mlbDebutDate'))

            await self.conn.execute("""
                UPDATE prospects
                SET
                    birth_date = COALESCE($1, birth_date),
                    birth_city = COALESCE($2, birth_city),
                    birth_country = COALESCE($3, birth_country),
                    height_inches = COALESCE($4, height_inches),
                    weight_lbs = COALESCE($5, weight_lbs),
                    draft_year = COALESCE($6, draft_year),
                    mlb_debut_date = COALESCE($7, mlb_debut_date),
                    updated_at = NOW()
                WHERE id = $8
            """,
                birth_date,  # Python date object!
                bio_data.get('birthCity'),
                bio_data.get('birthCountry'),
                height_inches,
                bio_data.get('weight'),
                bio_data.get('draftYear'),
                mlb_debut_date,  # Python date object!
                prospect_id
            )
            return True
        except Exception as e:
            print(f"[{self.season}] ERROR {prospect_id}: {e}")
            return False

    async def collect_birth_dates(self):
        print(f"\n[{self.season}] Starting collection...")

        all_players = await self.get_players_for_season()
        player_to_prospect, already_have = await self.get_prospects_with_player_ids()

        players_to_fetch = [
            pid for pid in all_players
            if pid in player_to_prospect and pid not in already_have
        ]

        print(f"[{self.season}] Need to fetch: {len(players_to_fetch)} players")

        if len(players_to_fetch) == 0:
            print(f"[{self.season}] Nothing to do!")
            return

        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        async with aiohttp.ClientSession(connector=connector) as session:
            for i, player_id in enumerate(players_to_fetch, 1):
                await asyncio.sleep(self.rate_limit_delay)

                bio_data = await self.fetch_player_bio(session, player_id)
                self.stats['api_calls_made'] += 1

                if bio_data and 'birthDate' in bio_data:
                    prospect_id = player_to_prospect[player_id]
                    success = await self.update_prospect(prospect_id, bio_data)
                    if success:
                        self.stats['successful'] += 1
                    else:
                        self.stats['failed'] += 1
                else:
                    self.stats['failed'] += 1

                if i % 50 == 0 or i == len(players_to_fetch):
                    elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (len(players_to_fetch) - i) / rate / 60 if rate > 0 else 0
                    print(f"[{self.season}] {i}/{len(players_to_fetch)} | "
                          f"Success: {self.stats['successful']} | "
                          f"Failed: {self.stats['failed']} | "
                          f"ETA: {eta:.1f}min")

        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        print(f"\n[{self.season}] DONE!")
        print(f"  API calls: {self.stats['api_calls_made']}")
        print(f"  Successful: {self.stats['successful']}")
        print(f"  Failed: {self.stats['failed']}")
        print(f"  Time: {elapsed/60:.1f} min")
        if self.stats['api_calls_made'] > 0:
            print(f"  Success rate: {self.stats['successful']/self.stats['api_calls_made']*100:.1f}%")

    async def run(self):
        try:
            await self.connect_db()
            await self.collect_birth_dates()
        finally:
            await self.disconnect_db()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', type=int, required=True)
    args = parser.parse_args()

    collector = BirthDateCollector(args.season)
    await collector.run()

if __name__ == "__main__":
    asyncio.run(main())
