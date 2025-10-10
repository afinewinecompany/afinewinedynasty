"""
Batch script to collect MiLB game logs for multiple seasons sequentially.

This script runs the collection for 2024, 2023, 2022, and 2021 seasons
in sequence, collecting AAA, AA, and A+ level data.
"""

import asyncio
import subprocess
import sys
from datetime import datetime


def run_collection(season: int, levels: list) -> bool:
    """Run collection for a single season."""
    print("=" * 80)
    print(f"Starting collection for {season} season")
    print(f"Levels: {', '.join(levels)}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    levels_str = ' '.join(levels)
    cmd = [
        sys.executable, '-m', 'scripts.collect_all_milb_gamelog',
        '--season', str(season),
        '--levels', *levels
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd='.',
            capture_output=False,
            text=True
        )

        if result.returncode == 0:
            print(f"\n✓ Successfully completed {season} season")
            return True
        else:
            print(f"\n✗ Failed to complete {season} season (exit code: {result.returncode})")
            return False

    except Exception as e:
        print(f"\n✗ Error running {season} season: {str(e)}")
        return False
    finally:
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80 + "\n")


def main():
    """Run collection for all seasons."""
    seasons = [2024, 2023, 2022, 2021]
    # Include all minor league levels: professional (AAA, AA, A+, A) and rookie (DSL, ROK, ACL)
    levels = ['AAA', 'AA', 'A+', 'A', 'DSL', 'ROK', 'ACL']

    print("\n" + "=" * 80)
    print("MiLB Game Log Collection - Multi-Season Batch Run")
    print("=" * 80)
    print(f"Seasons to process: {', '.join(map(str, seasons))}")
    print(f"Levels per season: {', '.join(levels)}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    results = {}

    for season in seasons:
        success = run_collection(season, levels)
        results[season] = success

        if not success:
            print(f"\n⚠️  Collection failed for {season}. Continuing to next season...\n")

    # Summary
    print("\n" + "=" * 80)
    print("BATCH COLLECTION SUMMARY")
    print("=" * 80)

    for season, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{season}: {status}")

    successful = sum(1 for s in results.values() if s)
    print(f"\nCompleted: {successful}/{len(seasons)} seasons")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
