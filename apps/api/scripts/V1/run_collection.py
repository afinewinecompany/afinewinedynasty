#!/usr/bin/env python
"""
Runner script for MiLB data collection.
Provides options to run full collection, test mode, or specific seasons.
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from collect_milb_all_seasons import MiLBSeasonCollector


async def test_collection():
    """Run a small test collection to verify everything works."""
    print("\nRUNNING TEST COLLECTION")
    print("=" * 60)
    print("This will collect data for a few teams from 2024 Triple-A")
    print("to verify the collection process works correctly.")
    print("=" * 60)

    collector = MiLBSeasonCollector()

    try:
        await collector.init_db()

        # Test with just one team
        teams = collector.get_season_teams(2024)

        # Filter to just Triple-A teams
        triple_a_teams = [t for t in teams if t.get('level') == 'Triple-A'][:2]  # Just 2 teams

        if not triple_a_teams:
            print("No Triple-A teams found for testing")
            return

        print(f"\nTesting with {len(triple_a_teams)} Triple-A teams from 2024:")
        for team in triple_a_teams:
            print(f"  - {team.get('name')}")

        print("\nStarting test collection...")

        for team in triple_a_teams:
            stats = await collector.collect_team_players(team, 2024)
            print(f"Team {team.get('name')}: {stats['players']} players, {stats['logs']} logs")

        print("\nTest collection completed successfully!")
        print("You can now run the full collection with: python run_collection.py --full")

    except Exception as e:
        print(f"\nTest failed: {e}")
    finally:
        await collector.close_db()


async def collect_specific_season(season: int):
    """Collect data for a specific season."""
    print(f"\nCOLLECTING DATA FOR {season} SEASON")
    print("=" * 60)

    collector = MiLBSeasonCollector()

    try:
        await collector.init_db()
        await collector.collect_season(season)
        print(f"\nCollection for {season} completed!")
    except Exception as e:
        print(f"\nCollection failed: {e}")
    finally:
        await collector.close_db()


async def full_collection():
    """Run the full collection for all seasons (2021-2025)."""
    print("\nSTARTING FULL MILB DATA COLLECTION (2021-2025)")
    print("=" * 60)
    print("This will collect comprehensive game logs for all minor league")
    print("players across all levels for seasons 2021-2025.")
    print("\nEstimated time: Several hours to days depending on rate limits")
    print("The collection will resume from checkpoint if interrupted.")
    print("=" * 60)

    response = input("\nDo you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Collection cancelled.")
        return

    collector = MiLBSeasonCollector()
    await collector.run_collection()


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='MiLB Data Collection Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a test collection (recommended first)
  python run_collection.py --test

  # Collect a specific season
  python run_collection.py --season 2024

  # Run full collection for all seasons
  python run_collection.py --full

  # Check collection status
  python check_collection_status.py
        """
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run a small test collection to verify setup'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full collection for all seasons (2021-2025)'
    )

    parser.add_argument(
        '--season',
        type=int,
        choices=[2021, 2022, 2023, 2024, 2025],
        help='Collect data for a specific season'
    )

    args = parser.parse_args()

    # Ensure at least one action is specified
    if not any([args.test, args.full, args.season]):
        print("Please specify an action: --test, --full, or --season YEAR")
        parser.print_help()
        sys.exit(1)

    # Run the appropriate collection
    if args.test:
        asyncio.run(test_collection())
    elif args.season:
        asyncio.run(collect_specific_season(args.season))
    elif args.full:
        asyncio.run(full_collection())


if __name__ == "__main__":
    main()