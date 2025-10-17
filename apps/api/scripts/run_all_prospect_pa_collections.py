#!/usr/bin/env python3
"""
Run PA collection for all seasons (2021-2025) concurrently.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from collect_prospect_pas import ProspectPACollector


async def collect_season(season: int, limit: int = None):
    """Collect PA data for one season."""
    try:
        collector = ProspectPACollector(season, limit)
        await collector.run()
        return (season, "SUCCESS", collector.collected_pas)
    except Exception as e:
        return (season, "FAILED", str(e))


async def main():
    parser = argparse.ArgumentParser(description='Run PA collections for all seasons')
    parser.add_argument('--seasons', nargs='+', type=int, default=[2021, 2022, 2023, 2024, 2025],
                       help='Seasons to collect (default: 2021-2025)')
    parser.add_argument('--limit', type=int, help='Limit prospects per season (for testing)')
    args = parser.parse_args()

    print("="*80)
    print("CONCURRENT PROSPECT PA COLLECTION")
    print("="*80)
    print(f"Start time: {datetime.now()}")
    print(f"Seasons: {args.seasons}")
    if args.limit:
        print(f"Limit: {args.limit} prospects per season")
    print("="*80)
    print()

    # Run all seasons concurrently
    tasks = [collect_season(season, args.limit) for season in args.seasons]
    results = await asyncio.gather(*tasks)

    print()
    print("="*80)
    print("ALL COLLECTIONS COMPLETE")
    print("="*80)
    print(f"End time: {datetime.now()}")
    print()
    print("Results:")
    for season, status, info in results:
        if status == "SUCCESS":
            print(f"  {season}: SUCCESS - {info} PAs collected")
        else:
            print(f"  {season}: FAILED - {info}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
