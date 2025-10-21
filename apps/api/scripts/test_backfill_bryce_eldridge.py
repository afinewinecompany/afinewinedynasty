"""
Test the comprehensive backfill script with Bryce Eldridge (MLB ID: 805811)

This should collect:
- CPX games
- AA games
- AAA games
- Full season, not just Sept 15-28

Expected: ~1,746 pitches across all levels
Current: 160 pitches (AA only, Sept 15-28)
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Import the collection functions from the comprehensive script
import sys
sys.path.append('.')
from comprehensive_pitch_backfill_2024 import (
    get_batter_games_with_levels,
    collect_game_pitches,
    insert_pitches_batch
)

async def test_bryce_eldridge():
    """Test collection for Bryce Eldridge"""

    bryce_id = 805811
    bryce_name = "Bryce Eldridge"

    print("\n" + "="*80)
    print(f"TEST: Bryce Eldridge (ID: {bryce_id})")
    print("="*80)

    # Check current data
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\nCURRENT DATA IN DATABASE (2024):")
    cur.execute("""
        SELECT
            level,
            COUNT(*) as pitch_count,
            COUNT(DISTINCT game_pk) as games,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2024
        GROUP BY level
        ORDER BY level
    """, (bryce_id,))

    existing_2024 = cur.fetchall()
    if existing_2024:
        for level, pitches, games, first_date, last_date in existing_2024:
            print(f"  {level}: {pitches} pitches from {games} games ({first_date} to {last_date})")
    else:
        print("  No 2024 data")

    print("\nCURRENT DATA IN DATABASE (2025):")
    cur.execute("""
        SELECT
            level,
            COUNT(*) as pitch_count,
            COUNT(DISTINCT game_pk) as games,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
        GROUP BY level
        ORDER BY level
    """, (bryce_id,))

    existing = cur.fetchall()
    if existing:
        for level, pitches, games, first_date, last_date in existing:
            print(f"  {level}: {pitches} pitches from {games} games ({first_date} to {last_date})")
    else:
        print("  No existing data")

    cur.close()
    conn.close()

    # Fetch games from API
    print("\nFETCHING GAMES FROM MLB STATS API:")

    connector = aiohttp.TCPConnector(limit=5)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        games = await get_batter_games_with_levels(session, bryce_id)

        if not games:
            print("  ERROR: No games found!")
            return

        print(f"\n  Found {len(games)} total games")

        # Group by level
        games_by_level = {}
        for game in games:
            level = game['level']
            if level not in games_by_level:
                games_by_level[level] = []
            games_by_level[level].append(game)

        print(f"\n  Breakdown by level:")
        for level, level_games in games_by_level.items():
            total_pas = sum(g['pas'] for g in level_games)
            print(f"    {level}: {len(level_games)} games, {total_pas} PAs")
            # Show first and last game
            dates = sorted([g['date'] for g in level_games])
            print(f"      Date range: {dates[0]} to {dates[-1]}")

        # Test collection for first game of each level
        print(f"\n  TESTING COLLECTION (first game per level):")

        for level, level_games in games_by_level.items():
            if not level_games:
                continue

            first_game = level_games[0]
            print(f"\n    Level {level} - Game {first_game['gamePk']} ({first_game['date']}):")

            pitches, error = await collect_game_pitches(session, bryce_id, first_game)

            if error:
                print(f"      ERROR: {error}")
            else:
                print(f"      SUCCESS: {len(pitches)} pitches collected")
                if pitches:
                    # Show sample pitch
                    sample = pitches[0]
                    print(f"      Sample: Pitcher {sample[1]}, {sample[9]} @ {sample[10]} mph, Zone {sample[12]}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNext step: Run comprehensive_pitch_backfill_2024.py to collect all games")

if __name__ == "__main__":
    asyncio.run(test_bryce_eldridge())
