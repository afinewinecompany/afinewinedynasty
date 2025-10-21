"""
Collect birth dates for the remaining 120 prospects with mlb_player_id
"""
import asyncio
import asyncpg
import aiohttp
from datetime import datetime, date
from typing import Optional, Dict
import time

class RemainingBirthDateCollector:
    def __init__(self):
        self.conn = None
        self.session = None
        self.success_count = 0
        self.fail_count = 0
        self.not_found_count = 0

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

    async def get_player_bio(self, player_id: str) -> Optional[Dict]:
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

    async def update_prospect(self, prospect_id: int, player_id: str, bio: Dict) -> bool:
        """Update existing prospect with birth date and bio data"""
        try:
            birth_date = self.parse_date(bio.get('birthDate'))
            height_inches = self.parse_height(bio.get('height'))
            mlb_debut_date = self.parse_date(bio.get('mlbDebutDate'))

            # Update existing prospect record
            await self.conn.execute("""
                UPDATE prospects
                SET
                    birth_date = COALESCE($1, birth_date),
                    birth_city = COALESCE($2, birth_city),
                    birth_country = COALESCE($3, birth_country),
                    height_inches = COALESCE($4, height_inches),
                    weight_lbs = COALESCE($5, weight_lbs),
                    mlb_debut_date = COALESCE($6, mlb_debut_date),
                    bats = COALESCE($7, bats),
                    throws = COALESCE($8, throws),
                    updated_at = NOW()
                WHERE id = $9
            """,
                birth_date,
                bio.get('birthCity'),
                bio.get('birthCountry'),
                height_inches,
                bio.get('weight'),
                mlb_debut_date,
                bio.get('batSide', {}).get('code'),
                bio.get('pitchHand', {}).get('code'),
                prospect_id
            )
            return True
        except Exception as e:
            print(f"ERROR updating {prospect_id}: {e}")
            return False

    async def process_prospect(self, prospect: dict, index: int, total: int):
        """Process a single prospect"""
        prospect_id = prospect['id']
        player_id = prospect['mlb_player_id']
        name = prospect['name']

        try:
            bio = await self.get_player_bio(player_id)

            if bio:
                birth_date_str = bio.get('birthDate', 'N/A')
                success = await self.update_prospect(prospect_id, player_id, bio)
                if success:
                    self.success_count += 1
                    position = bio.get('primaryPosition', {}).get('abbreviation', prospect['position'])
                    print(f"[{index}/{total}] OK {name:30} | ID: {player_id:7} | Born: {birth_date_str} | {position}")
                else:
                    self.fail_count += 1
                    print(f"[{index}/{total}] FAIL {name:30} | ID: {player_id:7} | Failed to update")
            else:
                self.not_found_count += 1
                print(f"[{index}/{total}] NOT FOUND {name:30} | ID: {player_id:7}")

            # Rate limiting: ~4 calls/sec
            await asyncio.sleep(0.25)

        except Exception as e:
            self.fail_count += 1
            print(f"[{index}/{total}] ERROR {name:30} | {e}")

    async def run(self):
        """Main collection process"""
        await self.connect()

        # Get prospects without birth dates but with mlb_player_id
        prospects = await self.conn.fetch("""
            SELECT id, mlb_player_id, name, position
            FROM prospects
            WHERE birth_date IS NULL
            AND mlb_player_id IS NOT NULL
            ORDER BY name
        """)

        total = len(prospects)
        print(f"Found {total} prospects without birth dates (but with MLB player ID)")
        print("=" * 80)
        print("Starting collection...\n")

        start_time = time.time()

        for i, prospect in enumerate(prospects, 1):
            await self.process_prospect(prospect, i, total)

        elapsed = time.time() - start_time

        print("\n" + "=" * 80)
        print("COLLECTION COMPLETE")
        print("=" * 80)
        print(f"Total prospects:      {total}")
        print(f"Successful:           {self.success_count}")
        print(f"Not found in API:     {self.not_found_count}")
        print(f"Failed:               {self.fail_count}")
        print(f"Time:                 {elapsed/60:.1f} minutes")
        if total > 0:
            print(f"Success rate:         {self.success_count/total*100:.1f}%")

        await self.close()

if __name__ == "__main__":
    collector = RemainingBirthDateCollector()
    asyncio.run(collector.run())
