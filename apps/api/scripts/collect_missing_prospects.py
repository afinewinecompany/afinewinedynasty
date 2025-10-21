"""
Collect MiLB data for missing prospects
Auto-generated collection script
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_milb_pbp import collect_player_season_pbp
from scripts.collect_milb_pitches import collect_player_season_pitches

async def collect_prospect_data(mlb_player_id, name, start_year=2021, end_year=2025):
    """Collect all data for a prospect"""

    print(f"\nCollecting data for {name} (ID: {mlb_player_id})")

    for year in range(start_year, end_year + 1):
        print(f"  Year {year}...")

        try:
            # Collect play-by-play
            pbp_count = await collect_player_season_pbp(mlb_player_id, year)
            print(f"    PBP: {pbp_count} plate appearances")

            # Collect pitch-by-pitch
            pitch_count = await collect_player_season_pitches(mlb_player_id, year)
            print(f"    Pitches: {pitch_count} pitches")

            # Small delay between years
            await asyncio.sleep(1)

        except Exception as e:
            print(f"    Error: {e}")

async def main():
    # Read prospects needing collection
    needs_df = pd.read_csv('top_100_collection_needs_*.csv')

    # Filter for prospects that need data
    to_collect = needs_df[needs_df['status'].isin(['NO DATA', 'NEEDS PBP', 'NEEDS PITCH'])]
    to_collect = to_collect[to_collect['mlb_id'].notna()]

    print(f"Collecting data for {len(to_collect)} prospects...")

    for idx, row in to_collect.iterrows():
        await collect_prospect_data(
            mlb_player_id=int(row['mlb_id']),
            name=row['name']
        )

        # Delay between players
        await asyncio.sleep(2)

    print("\nCollection complete!")

if __name__ == "__main__":
    asyncio.run(main())
