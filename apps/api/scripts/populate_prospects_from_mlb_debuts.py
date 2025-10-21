"""
Populate Prospects Table from MLB Debuts (2021-2025)
=====================================================

This script adds the 1,010 missing MLB players to the prospects table
by fetching their metadata from the MLB Stats API.

Strategy:
1. Get list of MLB player IDs not in prospects table
2. Fetch player details from MLB Stats API
3. Insert into prospects table with proper metadata

Usage:
    python scripts/populate_prospects_from_mlb_debuts.py
"""

import asyncio
import asyncpg
import aiohttp
from datetime import datetime
import sys
import codecs
from typing import Optional, Dict, Any
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


async def get_missing_players(conn):
    """Get list of MLB players not in prospects table."""

    query = """
        WITH mlb_debuts_2021_2025 AS (
            SELECT
                mlb_player_id,
                MIN(season) as debut_season,
                COUNT(*) as mlb_games
            FROM mlb_game_logs
            WHERE season BETWEEN 2021 AND 2025
            GROUP BY mlb_player_id
            HAVING COUNT(*) >= 20  -- At least 20 games
        )
        SELECT
            mlb.mlb_player_id,
            mlb.debut_season,
            mlb.mlb_games
        FROM mlb_debuts_2021_2025 mlb
        WHERE NOT EXISTS (
            SELECT 1 FROM prospects p
            WHERE p.mlb_player_id::integer = mlb.mlb_player_id
        )
        ORDER BY mlb.mlb_games DESC
    """

    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def fetch_player_metadata(session: aiohttp.ClientSession, mlb_player_id: int) -> Optional[Dict[str, Any]]:
    """Fetch player metadata from MLB Stats API."""

    url = f"{MLB_API_BASE}/people/{mlb_player_id}"

    try:
        await asyncio.sleep(0.1)  # Rate limiting
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()

                if 'people' in data and len(data['people']) > 0:
                    player = data['people'][0]

                    # Extract relevant fields
                    return {
                        'mlb_player_id': mlb_player_id,
                        'name': player.get('fullName', 'Unknown'),
                        'first_name': player.get('firstName', ''),
                        'last_name': player.get('lastName', ''),
                        'birth_date': player.get('birthDate'),
                        'birth_city': player.get('birthCity'),
                        'birth_state': player.get('birthStateProvince'),
                        'birth_country': player.get('birthCountry'),
                        'height': player.get('height'),
                        'weight': player.get('weight'),
                        'position': player.get('primaryPosition', {}).get('abbreviation', 'Unknown'),
                        'bat_side': player.get('batSide', {}).get('code'),
                        'pitch_hand': player.get('pitchHand', {}).get('code'),
                        'mlb_debut_date': player.get('mlbDebutDate'),
                        'draft_year': player.get('draftYear'),
                        'draft_round': player.get('draftRound'),
                        'draft_pick': player.get('draftPick'),
                    }

            return None

    except Exception as e:
        print(f"  Error fetching player {mlb_player_id}: {e}")
        return None


async def insert_prospect(conn, player_data: Dict[str, Any], debut_season: int):
    """Insert player into prospects table."""

    try:
        # First check if prospect already exists
        check_query = "SELECT id FROM prospects WHERE mlb_player_id = $1"
        existing = await conn.fetchrow(check_query, str(player_data['mlb_player_id']))

        if existing:
            return False  # Already exists, skip

        # Insert new prospect
        query = """
            INSERT INTO prospects (
                mlb_player_id,
                name,
                position,
                birth_date,
                height_inches,
                weight_lbs,
                bats,
                throws,
                birth_city,
                birth_country,
                draft_year,
                mlb_debut_date,
                created_at,
                updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW()
            )
            RETURNING id
        """
        # Parse birth_date if exists
        birth_date = None
        if player_data.get('birth_date'):
            try:
                birth_date = datetime.strptime(player_data['birth_date'], '%Y-%m-%d').date()
            except:
                pass

        # Parse MLB debut date
        mlb_debut_date = None
        if player_data.get('mlb_debut_date'):
            try:
                mlb_debut_date = datetime.strptime(player_data['mlb_debut_date'], '%Y-%m-%d').date()
            except:
                pass

        # Parse height (e.g., "6' 2\"" -> 74 inches)
        height_inches = None
        if player_data.get('height'):
            try:
                height_str = player_data['height']
                parts = height_str.replace('"', '').replace("'", ' ').split()
                if len(parts) >= 2:
                    feet = int(parts[0])
                    inches = int(parts[1])
                    height_inches = (feet * 12) + inches
            except:
                pass

        result = await conn.fetchrow(
            query,
            str(player_data['mlb_player_id']),
            player_data['name'],
            player_data['position'],
            birth_date,
            height_inches,
            player_data.get('weight'),
            player_data.get('bat_side'),
            player_data.get('pitch_hand'),
            player_data.get('birth_city'),
            player_data.get('birth_country'),
            player_data.get('draft_year'),
            mlb_debut_date,
        )

        return result is not None

    except Exception as e:
        print(f"  Error inserting {player_data['name']}: {e}")
        return False


async def populate_prospects():
    """Main function to populate prospects table."""

    print("="*80)
    print("POPULATE PROSPECTS TABLE FROM MLB DEBUTS")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Step 1: Get missing players
        print("="*80)
        print("1. IDENTIFYING MISSING PLAYERS")
        print("="*80)

        missing_players = await get_missing_players(conn)

        print(f"\nMissing MLB players (2021-2025, 20+ games): {len(missing_players)}")

        if not missing_players:
            print("\n✅ All MLB players already in prospects table!")
            return

        print(f"\nTop 10 by MLB games:")
        for i, player in enumerate(missing_players[:10], 1):
            print(f"  {i}. MLB Player ID: {player['mlb_player_id']} - {player['mlb_games']} games (debut: {player['debut_season']})")

        # Step 2: Fetch metadata and insert
        print("\n" + "="*80)
        print("2. FETCHING PLAYER METADATA & INSERTING INTO DATABASE")
        print("="*80)

        async with aiohttp.ClientSession() as session:
            inserted = 0
            failed = 0

            for i, player in enumerate(missing_players, 1):
                if i % 50 == 0:
                    print(f"\n  Progress: {i}/{len(missing_players)} ({i/len(missing_players)*100:.1f}%)")

                if i % 10 == 0:
                    print(f"    Inserted: {inserted}, Failed: {failed}")

                # Fetch metadata
                metadata = await fetch_player_metadata(session, player['mlb_player_id'])

                if metadata:
                    # Insert into database
                    success = await insert_prospect(conn, metadata, player['debut_season'])

                    if success:
                        inserted += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                    print(f"    Failed to fetch metadata for player {player['mlb_player_id']}")

        # Step 3: Verify results
        print("\n" + "="*80)
        print("3. VERIFICATION")
        print("="*80)

        # Count prospects after insertion
        total_prospects = await conn.fetchval("SELECT COUNT(*) FROM prospects")
        prospects_with_mlb_id = await conn.fetchval("""
            SELECT COUNT(*)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            AND mlb_player_id ~ '^[0-9]+$'
        """)

        print(f"\nTotal prospects in table: {total_prospects}")
        print(f"Prospects with MLB Player ID: {prospects_with_mlb_id}")

        # Check how many MLB players are still missing
        still_missing = await conn.fetch("""
            WITH mlb_debuts AS (
                SELECT DISTINCT mlb_player_id
                FROM mlb_game_logs
                WHERE season BETWEEN 2021 AND 2025
                GROUP BY mlb_player_id
                HAVING COUNT(*) >= 20
            )
            SELECT COUNT(*) as missing_count
            FROM mlb_debuts mlb
            WHERE NOT EXISTS (
                SELECT 1 FROM prospects p
                WHERE p.mlb_player_id::integer = mlb.mlb_player_id
            )
        """)

        still_missing_count = still_missing[0]['missing_count']

        print(f"\nInsertion Results:")
        print(f"  ✅ Successfully inserted: {inserted}")
        print(f"  ❌ Failed to insert: {failed}")
        print(f"  ⚠️  Still missing: {still_missing_count}")

        if still_missing_count > 0:
            print(f"\nNote: {still_missing_count} players could not be added (API errors or missing data)")

        # Step 4: Summary
        print("\n" + "="*80)
        print("4. SUMMARY")
        print("="*80)

        print(f"""
BEFORE:
- Prospects in table: {total_prospects - inserted}
- MLB players (2021-2025) in prospects: {prospects_with_mlb_id - inserted}
- Missing: {len(missing_players)}

AFTER:
- Prospects in table: {total_prospects}
- MLB players (2021-2025) in prospects: {prospects_with_mlb_id}
- Missing: {still_missing_count}

IMPACT ON TRAINING DATA:
- Expected new training samples: {inserted - still_missing_count}
- (Assuming they have MiLB data available)

NEXT STEPS:
1. Re-run training data builder to extract new samples
2. Expected training samples: 22 → {22 + (inserted - still_missing_count)} (+{((inserted - still_missing_count) / 22 * 100):.0f}% increase)
        """)

    finally:
        await conn.close()

    print("\n" + "="*80)
    print("PROSPECTS TABLE POPULATION COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(populate_prospects())
