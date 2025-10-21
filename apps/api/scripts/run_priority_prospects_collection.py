"""
Priority collection for Top 100 prospects
Focus on collecting missing data for highest-ranked prospects
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
import logging

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import get_db_sync
from scripts.collect_milb_pbp_data import MiLBPitchByPitchCollector
from sqlalchemy import text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'priority_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# PRIORITY 1: Top prospects with NO data at all (2024-2025 focus)
TOP_PROSPECTS_NO_DATA = [
    {'rank': 6, 'name': 'Samuel Basallo', 'mlb_player_id': 694212},
    {'rank': 7, 'name': 'Bryce Eldridge', 'mlb_player_id': 805811},
    {'rank': 13, 'name': 'Nolan McLean', 'mlb_player_id': 690997},
    {'rank': 20, 'name': 'Payton Tolle', 'mlb_player_id': 801139},
    {'rank': 21, 'name': 'Bubba Chandler', 'mlb_player_id': 696149},
    {'rank': 22, 'name': 'Trey Yesavage', 'mlb_player_id': 702056},
    {'rank': 23, 'name': 'Jonah Tong', 'mlb_player_id': 804636},
    {'rank': 25, 'name': 'Carter Jensen', 'mlb_player_id': 695600},
    {'rank': 26, 'name': 'Thomas White', 'mlb_player_id': 806258},
    {'rank': 27, 'name': 'Connelly Early', 'mlb_player_id': 813349},
]

# PRIORITY 2: Top prospects needing pitch data (includes #1 and #2!)
TOP_PROSPECTS_NEED_PITCH = [
    {'rank': 1, 'name': 'Konnor Griffin', 'mlb_player_id': 804606},
    {'rank': 2, 'name': 'Kevin McGonigle', 'mlb_player_id': 805808},
    {'rank': 3, 'name': 'Jesus Made', 'mlb_player_id': 815908},
    {'rank': 4, 'name': 'Leo De Vries', 'mlb_player_id': 815888},
    {'rank': 8, 'name': 'JJ Wetherholt', 'mlb_player_id': 802139},
]

async def collect_for_prospect(collector, db, prospect, seasons):
    """Collect data for a single prospect"""
    try:
        logger.info(f"  Collecting for {prospect['name']} (Rank #{prospect['rank']})")

        games_collected = await collector.collect_prospect_games(
            db,
            prospect,
            seasons
        )

        if games_collected > 0:
            logger.info(f"    ✓ Collected {games_collected} games")
        else:
            logger.info(f"    - No new games found")

        return games_collected

    except Exception as e:
        logger.error(f"    ✗ Error: {e}")
        return 0

async def main():
    """Main collection runner"""

    print("=" * 70)
    print("PRIORITY PROSPECT DATA COLLECTION")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    db = get_db_sync()

    try:
        async with MiLBPitchByPitchCollector() as collector:
            # Reduce delay for faster collection
            collector.request_delay = 0.3

            total_collected = 0
            start_time = time.time()

            # PHASE 1: Collect for prospects with NO data
            print("\n=== PHASE 1: TOP PROSPECTS WITH NO DATA ===")
            print("Focusing on 2024-2025 seasons for recent performance\n")

            for i, prospect in enumerate(TOP_PROSPECTS_NO_DATA[:5], 1):  # Start with top 5
                print(f"[{i}/5] Rank #{prospect['rank']}: {prospect['name']}")

                games = await collect_for_prospect(
                    collector,
                    db,
                    prospect,
                    [2024, 2025]  # Focus on recent seasons
                )
                total_collected += games

                # Small delay between prospects
                await asyncio.sleep(1)

            # PHASE 2: Collect pitch data for top prospects
            print("\n=== PHASE 2: TOP PROSPECTS NEEDING PITCH DATA ===")
            print("Including #1 and #2 ranked prospects!\n")

            for i, prospect in enumerate(TOP_PROSPECTS_NEED_PITCH, 1):
                print(f"[{i}/{len(TOP_PROSPECTS_NEED_PITCH)}] Rank #{prospect['rank']}: {prospect['name']}")

                # Check if they already have PBP data
                check_query = text("""
                    SELECT COUNT(*) as pbp_count
                    FROM milb_plate_appearances
                    WHERE mlb_player_id = :player_id
                    AND season IN (2024, 2025)
                """)

                result = db.execute(check_query, {'player_id': prospect['mlb_player_id']})
                pbp_count = result.scalar()

                if pbp_count > 0:
                    logger.info(f"  Already has {pbp_count} PAs, focusing on pitch data")

                games = await collect_for_prospect(
                    collector,
                    db,
                    prospect,
                    [2024, 2025]
                )
                total_collected += games

                await asyncio.sleep(1)

            # Summary
            elapsed = time.time() - start_time

            print("\n" + "=" * 70)
            print("COLLECTION SUMMARY")
            print("=" * 70)
            print(f"Total games collected: {total_collected}")
            print(f"Total errors: {collector.errors}")
            print(f"Time elapsed: {elapsed/60:.1f} minutes")

            # Verify what was collected
            print("\n=== VERIFYING DATABASE ===")

            for prospect in TOP_PROSPECTS_NO_DATA[:3]:
                query = text("""
                    SELECT
                        COUNT(DISTINCT game_pk) as games,
                        COUNT(*) as plate_appearances
                    FROM milb_plate_appearances
                    WHERE mlb_player_id = :player_id
                    AND season IN (2024, 2025)
                """)

                result = db.execute(query, {'player_id': prospect['mlb_player_id']}).fetchone()

                if result and result[0] > 0:
                    print(f"✓ {prospect['name']}: {result[0]} games, {result[1]} PAs")
                else:
                    print(f"✗ {prospect['name']}: No data collected")

            print("\n✓ Collection complete! Check logs for details.")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n✗ Collection failed: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())