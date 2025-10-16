"""
Run all pitch-by-pitch collections concurrently.

This script runs all 5 season collection scripts simultaneously to maximize
data collection speed. Each season runs in its own process.

Usage:
    python run_all_pitch_collections.py --test    # Run with limit of 5 players per season
    python run_all_pitch_collections.py           # Full collection
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SEASONS = [2021, 2022, 2023, 2024, 2025]


async def run_collection(season: int, limit: int = None):
    """Run collection for a single season."""
    script = f"collect_pitch_data_{season}.py"
    script_path = Path(__file__).parent / script

    cmd = [sys.executable, str(script_path)]
    if limit:
        cmd.extend(['--limit', str(limit)])

    print(f"[{season}] Starting collection...")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        print(f"[{season}] ✓ Collection complete!")
    else:
        print(f"[{season}] ✗ Collection failed!")
        print(f"[{season}] Error: {stderr.decode()}")

    return proc.returncode


async def main():
    parser = argparse.ArgumentParser(
        description="Run all pitch-by-pitch collections concurrently"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: run with 5 players per season'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit players per season'
    )
    parser.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        default=SEASONS,
        help='Specific seasons to run (e.g., 2021 2022)'
    )

    args = parser.parse_args()

    limit = 5 if args.test else args.limit

    print("="*80)
    print("CONCURRENT PITCH-BY-PITCH DATA COLLECTION")
    print("="*80)
    print(f"Start time: {datetime.now()}")
    print(f"Seasons: {args.seasons}")
    if limit:
        print(f"Limit: {limit} players per season")
    print("="*80)
    print()

    # Run all collections concurrently
    start_time = asyncio.get_event_loop().time()

    tasks = [run_collection(season, limit) for season in args.seasons]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = asyncio.get_event_loop().time() - start_time

    print()
    print("="*80)
    print("ALL COLLECTIONS COMPLETE")
    print("="*80)
    print(f"End time: {datetime.now()}")
    print(f"Total time: {elapsed:.1f}s")
    print()

    # Summary
    for season, result in zip(args.seasons, results):
        if isinstance(result, Exception):
            print(f"{season}: ✗ FAILED - {result}")
        elif result == 0:
            print(f"{season}: ✓ SUCCESS")
        else:
            print(f"{season}: ✗ FAILED (exit code {result})")

    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
