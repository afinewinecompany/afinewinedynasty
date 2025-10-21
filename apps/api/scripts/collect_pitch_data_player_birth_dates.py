"""
Collect birth dates for players with pitch data who are NOT in prospects table
These are likely MLB players or non-prospect MiLB players with detailed tracking
"""
import asyncio
import asyncpg
import aiohttp
from datetime import datetime, date
from typing import Optional, Dict
import time

class PitchDataPlayerCollector:
    def __init__(self):
        self.conn = None
        self.session = None
        self.success_count = 0
        self.fail_count = 0
        self.added_to_prospects = 0

    async def connect(self):
        self.conn = await asyncpg.connect(
            host="nozomi.proxy.rlwy.net",
            port=39235,
            user="postgres",
            password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
            database="railway"
        )
        self.session = aiohttp.ClientSession()
        print("Connected to database and API\n")

    async def close(self):
        if self.conn:
            await self.conn.close()
        if self.session:
            await self.session.close()

    def parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Convert '1994-11-09' to Python date object"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None

    def parse_height(self, height_str: Optional[str]) -> Optional[int]:
        """Convert height like 6' 2\" to inches"""
        if not height_str:
            return None
        try:
            parts = height_str.replace('"', '').split("'")
            if len(parts) == 2:
                feet = int(parts[0].strip())
                inches = int(parts[1].strip()) if parts[1].strip() else 0
                return feet * 12 + inches
        except:
            return None

    async def get_player_bio(self, player_id: int) -> Optional[Dict]:
        """Fetch player biographical data from MLB Stats API"""
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'people' in data and len(data['people']) > 0:
                        return data['people'][0]
        except Exception as e:
            print(f"ERROR fetching {player_id}: {e}")
        return None

    async def add_to_prospects(self, player_id: int, bio: Dict) -> bool:
        """Add player to prospects table with their bio data"""
        try:
            birth_date = self.parse_date(bio.get('birthDate'))
            height_inches = self.parse_height(bio.get('height'))
            mlb_debut_date = self.parse_date(bio.get('mlbDebutDate'))

            # Simple INSERT - these players don't exist in prospects yet
            await self.conn.execute("""
                INSERT INTO prospects (
                    mlb_player_id,
                    name,
                    position,
                    bats,
                    throws,
                    birth_date,
                    birth_city,
                    birth_country,
                    height_inches,
                    weight_lbs,
                    mlb_debut_date,
                    current_organization,
                    created_at,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW()
                )
            """,
                str(player_id),  # mlb_player_id
                bio.get('fullName'),  # name
                bio.get('primaryPosition', {}).get('abbreviation'),  # position
                bio.get('batSide', {}).get('code'),  # bats
                bio.get('pitchHand', {}).get('code'),  # throws
                birth_date,
                bio.get('birthCity'),
                bio.get('birthCountry'),
                height_inches,
                bio.get('weight'),
                mlb_debut_date,
                bio.get('currentTeam', {}).get('name')  # organization
            )
            return True
        except Exception as e:
            print(f"ERROR inserting {player_id}: {e}")
            return False

    async def process_player(self, player_id: int, index: int, total: int):
        """Process a single player"""
        try:
            bio = await self.get_player_bio(player_id)

            if bio:
                success = await self.add_to_prospects(player_id, bio)
                if success:
                    self.success_count += 1
                    self.added_to_prospects += 1
                    name = bio.get('fullName', 'Unknown')
                    position = bio.get('primaryPosition', {}).get('abbreviation', '?')
                    birth_date = bio.get('birthDate', 'N/A')
                    print(f"[{index}/{total}] OK {player_id} - {name} ({position}) - Born: {birth_date}")
                else:
                    self.fail_count += 1
                    print(f"[{index}/{total}] FAIL {player_id} - Failed to insert")
            else:
                self.fail_count += 1
                print(f"[{index}/{total}] FAIL {player_id} - No API data")

            # Rate limiting: ~4 calls/sec
            await asyncio.sleep(0.25)

        except Exception as e:
            self.fail_count += 1
            print(f"[{index}/{total}] ERROR {player_id}: {e}")

    async def run(self):
        """Main collection process"""
        await self.connect()

        # Get all players with pitch data NOT in prospects
        missing_players = await self.conn.fetch("""
            SELECT DISTINCT player_id::integer as player_id FROM (
                SELECT mlb_pitcher_id::text as player_id
                FROM milb_pitcher_pitches
                WHERE mlb_pitcher_id IS NOT NULL
                UNION
                SELECT mlb_batter_id::text as player_id
                FROM milb_batter_pitches
                WHERE mlb_batter_id IS NOT NULL
            ) pitch_players
            WHERE player_id NOT IN (
                SELECT mlb_player_id::text
                FROM prospects
                WHERE mlb_player_id IS NOT NULL
            )
            ORDER BY player_id
        """)

        total = len(missing_players)
        print(f"Found {total} players with pitch data not in prospects table\n")
        print("=" * 70)
        print("Starting collection...\n")

        start_time = time.time()

        for i, row in enumerate(missing_players, 1):
            await self.process_player(row['player_id'], i, total)

        elapsed = time.time() - start_time

        print("\n" + "=" * 70)
        print("COLLECTION COMPLETE")
        print("=" * 70)
        print(f"Total players:        {total}")
        print(f"Successful:           {self.success_count}")
        print(f"Failed:               {self.fail_count}")
        print(f"Added to prospects:   {self.added_to_prospects}")
        print(f"Time:                 {elapsed/60:.1f} minutes")
        print(f"Success rate:         {self.success_count/total*100:.1f}%")

        await self.close()

if __name__ == "__main__":
    collector = PitchDataPlayerCollector()
    asyncio.run(collector.run())
