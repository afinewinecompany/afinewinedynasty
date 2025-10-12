#!/usr/bin/env python
"""
Collect MiLB play-by-play data for 2021 season with proper environment loading.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables FIRST
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Now import after environment is loaded
from sqlalchemy import create_engine, text
import aiohttp

def get_db_connection():
    """Get database connection with proper URL conversion"""
    db_url = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')

    if not db_url:
        raise ValueError("No database URL found in environment")

    # Convert async URL to sync
    if 'postgresql+asyncpg://' in db_url:
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

    return create_engine(db_url)

async def collect_player_pbp_2021(session, player_id, player_name):
    """Collect 2021 play-by-play data for a single player"""
    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # Get player's 2021 games across all MiLB levels
    sport_ids = [11, 12, 13, 14, 15, 16, 21]  # All MiLB levels
    all_games = []

    for sport_id in sport_ids:
        url = f"{BASE_URL}/people/{player_id}/stats?stats=gameLog&season=2021&sportId={sport_id}&group=hitting,pitching"

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'stats' in data and data['stats']:
                        for stat_group in data['stats']:
                            splits = stat_group.get('splits', [])
                            for split in splits:
                                if 'game' in split:
                                    all_games.append(split['game']['gamePk'])
        except Exception as e:
            print(f"    Error fetching games for sport {sport_id}: {e}")

    unique_games = list(set(all_games))

    if not unique_games:
        print(f"    No 2021 games found")
        return 0

    print(f"    Found {len(unique_games)} games in 2021")

    # Collect play-by-play for each game
    plays_collected = 0

    for game_pk in unique_games[:10]:  # Limit to first 10 games for testing
        url = f"{BASE_URL}/game/{game_pk}/feed/live"

        try:
            await asyncio.sleep(0.3)  # Rate limiting
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Extract play-by-play data
                    all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                    for play in all_plays:
                        # Check if this player was involved
                        if 'matchup' in play:
                            batter_id = play['matchup'].get('batter', {}).get('id')
                            pitcher_id = play['matchup'].get('pitcher', {}).get('id')

                            if batter_id == player_id or pitcher_id == player_id:
                                plays_collected += 1
                                # Here you would save to database
                                # For now, just count

        except Exception as e:
            print(f"    Error fetching game {game_pk}: {e}")

    return plays_collected

async def main():
    print("="*70)
    print("MiLB PLAY-BY-PLAY COLLECTION FOR 2021")
    print("="*70)
    print(f"Start time: {datetime.now()}")
    print()

    # Get database connection
    engine = get_db_connection()

    # Get players who need 2021 data
    with engine.connect() as conn:
        # Find players who played in 2021 but have no plate appearance data
        result = conn.execute(text("""
            SELECT DISTINCT
                p.mlb_player_id::integer as player_id,
                p.name,
                p.organization
            FROM prospects p
            INNER JOIN milb_game_logs g ON p.mlb_player_id = g.mlb_player_id::text
            WHERE g.season = 2021
            AND p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            AND NOT EXISTS (
                SELECT 1
                FROM milb_plate_appearances pa
                WHERE pa.mlb_player_id = p.mlb_player_id::integer
                AND pa.season = 2021
            )
            ORDER BY p.name
            LIMIT 10
        """))

        players = list(result)

    if not players:
        print("No players found needing 2021 data")
        return

    print(f"Found {len(players)} players needing 2021 play-by-play data")
    print()

    # Create HTTP session
    async with aiohttp.ClientSession() as session:
        for i, (player_id, name, org) in enumerate(players, 1):
            print(f"[{i}/{len(players)}] {name} ({org}) - ID: {player_id}")

            try:
                plays = await collect_player_pbp_2021(session, player_id, name)
                print(f"    Collected {plays} plays")
            except Exception as e:
                print(f"    ERROR: {e}")

            # Small delay between players
            await asyncio.sleep(1)

    print()
    print("="*70)
    print("COLLECTION COMPLETE")
    print(f"End time: {datetime.now()}")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())