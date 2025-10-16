#!/usr/bin/env python3
"""
Test MLB Stats API for specific prospects to verify data availability.
"""

import sys
import os
import asyncio
import aiohttp
from pathlib import Path
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

BASE_URL = "https://statsapi.mlb.com/api/v1"
MILB_SPORT_IDS = {
    11: 'AAA',
    12: 'AA',
    13: 'High-A',
    14: 'Single-A',
    15: 'Rookie',
    16: 'Rookie Advanced',
    21: 'Complex/DSL'
}

async def fetch_json(session, url: str):
    """Fetch JSON data from URL."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

async def test_prospect_data(player_id: int, name: str, season: int):
    """Test if we can find game data for a specific prospect/season."""
    print(f"\n{'='*80}")
    print(f"Testing: {name} (ID: {player_id}) - Season: {season}")
    print(f"{'='*80}")

    async with aiohttp.ClientSession() as session:
        games_found = {}

        # Try each sport ID
        for sport_id, level_name in MILB_SPORT_IDS.items():
            url = f"{BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting,pitching&sportId={sport_id}"
            print(f"\n[{level_name}] {url}")

            data = await fetch_json(session, url)

            if not data or not isinstance(data, dict):
                print(f"  [X] No data returned")
                continue

            stats = data.get('stats', [])
            if not stats:
                print(f"  [X] No stats")
                continue

            total_games = 0
            for stat_group in stats:
                splits = stat_group.get('splits', [])
                total_games += len(splits)

                for split in splits[:3]:  # Show first 3 games
                    game = split.get('game', {})
                    game_pk = game.get('gamePk')
                    game_date = split.get('date')
                    if game_pk:
                        games_found[game_pk] = {
                            'pk': game_pk,
                            'date': game_date,
                            'level': level_name
                        }
                        print(f"  [OK] Game {game_pk} on {game_date}")

            if total_games > 3:
                print(f"  ... and {total_games - 3} more games")

        # Now test if we can get play-by-play for found games
        if games_found:
            print(f"\n[Testing Play-by-Play Access]")
            tested_count = 0
            success_count = 0

            for game_pk, game_info in list(games_found.items())[:5]:  # Test up to 5 games
                tested_count += 1
                pbp_url = f"{BASE_URL}/game/{game_pk}/feed/live"
                print(f"  Game {game_pk} ({game_info['date']}):")

                pbp_data = await fetch_json(session, pbp_url)

                if not pbp_data:
                    print(f"    [X] No feed/live data, trying playByPlay...")
                    pbp_url = f"{BASE_URL}/game/{game_pk}/playByPlay"
                    pbp_data = await fetch_json(session, pbp_url)

                if pbp_data and isinstance(pbp_data, dict):
                    # Check for plays
                    if 'liveData' in pbp_data:
                        all_plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
                    else:
                        all_plays = pbp_data.get('allPlays', [])

                    if all_plays:
                        # Count plays for this player
                        player_plays = [p for p in all_plays if p.get('matchup', {}).get('batter', {}).get('id') == player_id]
                        success_count += 1
                        print(f"    [OK] Found {len(all_plays)} total plays, {len(player_plays)} for this player")
                    else:
                        print(f"    [X] No plays in response")
                else:
                    print(f"    [X] No playByPlay data available")

            print(f"\n[Summary]")
            print(f"  Games found in game log: {len(games_found)}")
            print(f"  Games tested for PBP: {tested_count}")
            print(f"  Games with PBP data: {success_count}")
            print(f"  PBP Success Rate: {success_count/tested_count*100:.1f}%")
        else:
            print(f"\n[Summary]")
            print(f"  [X] NO GAMES FOUND - This prospect has no game logs in MLB Stats API for {season}")

async def main():
    """Test API availability for sample prospects."""

    # Get sample prospects from CSV
    sample_file = Path(__file__).parent / "sample_missing_prospects.csv"
    if not sample_file.exists():
        print(f"ERROR: {sample_file} not found. Run analyze_pa_coverage.py first.")
        return

    df = pd.read_csv(sample_file)

    print("\n" + "="*80)
    print("MLB Stats API Availability Test")
    print("="*80)
    print(f"\nTesting {len(df)} prospects without PA data...")
    print("This will verify if the MLB Stats API actually has data for these players.")

    # Test first 5 prospects across different seasons
    for idx, row in df.head(5).iterrows():
        player_id = int(row['mlb_player_id'])
        name = row['name']
        first_season = int(row['first_season'])
        last_season = int(row['last_season'])

        # Test most recent season
        await test_prospect_data(player_id, name, last_season)

        await asyncio.sleep(1)  # Rate limiting

    print("\n" + "="*80)
    print("API Testing Complete!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
