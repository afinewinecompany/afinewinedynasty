#!/usr/bin/env python
"""
Run complete MLB collections for both 2024 and 2025 seasons.
This script launches all necessary collections in parallel for maximum efficiency.

Usage:
    python run_all_collections_2024_2025.py           # Full collection for both years
    python run_all_collections_2024_2025.py --test    # Test with 5 players per collection
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import os

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

# Change to API directory for proper imports
os.chdir(api_dir)

from sqlalchemy import text
from app.db.database import sync_engine


def check_collection_status():
    """Check current collection status for both years."""
    print("\n" + "="*80)
    print("CURRENT COLLECTION STATUS")
    print("="*80)

    with sync_engine.connect() as conn:
        for year in [2024, 2025]:
            print(f"\n--- {year} SEASON ---")

            # Check play-by-play data
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_pas,
                    COUNT(DISTINCT mlb_player_id) as unique_players,
                    MIN(game_date) as first_date,
                    MAX(game_date) as last_date
                FROM milb_plate_appearances
                WHERE season = :year
            """), {"year": year})
            row = result.fetchone()

            print(f"Play-by-Play (Plate Appearances):")
            print(f"  Total PAs: {row.total_pas:,}")
            print(f"  Unique players: {row.unique_players:,}")
            if row.first_date:
                print(f"  Date range: {row.first_date} to {row.last_date}")

            # Check batter pitch data
            try:
                result = conn.execute(text("""
                    SELECT
                        COUNT(*) as total_pitches,
                        COUNT(DISTINCT mlb_batter_id) as unique_batters
                    FROM milb_batter_pitches
                    WHERE season = :year
                """), {"year": year})
                row = result.fetchone()
                print(f"Batter Pitch-by-Pitch:")
                print(f"  Total pitches: {row.total_pitches:,}")
                print(f"  Unique batters: {row.unique_batters:,}")
            except:
                print(f"Batter Pitch-by-Pitch: Table not found")

            # Check pitcher pitch data
            try:
                result = conn.execute(text("""
                    SELECT
                        COUNT(*) as total_pitches,
                        COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
                    FROM milb_pitcher_pitches
                    WHERE season = :year
                """), {"year": year})
                row = result.fetchone()
                print(f"Pitcher Pitch-by-Pitch:")
                print(f"  Total pitches: {row.total_pitches:,}")
                print(f"  Unique pitchers: {row.unique_pitchers:,}")
            except:
                print(f"Pitcher Pitch-by-Pitch: Table not found")

            # Count total players needing collection
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT mlb_player_id) as total
                FROM milb_game_logs
                WHERE season = :year
                AND mlb_player_id IS NOT NULL
            """), {"year": year})
            total_players = result.scalar()
            print(f"Total players with {year} games: {total_players:,}")


async def run_collection(script_name: str, year: int, collection_type: str, limit: int = None):
    """Run a specific collection asynchronously."""
    script_path = script_dir / script_name

    if not script_path.exists():
        print(f"[{year} {collection_type}] Script not found: {script_name}")
        return 1

    cmd = [sys.executable, str(script_path)]
    if limit:
        cmd.extend(['--limit', str(limit)])

    label = f"{year} {collection_type}"
    print(f"[{label}] Starting collection...")
    print(f"[{label}] Command: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Collect output but don't print everything (too verbose)
    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        print(f"[{label}] [OK] Collection complete!")
        # Print last few lines of output for summary
        lines = stdout.decode().split('\n')
        if len(lines) > 5:
            print(f"[{label}] Summary:")
            for line in lines[-5:]:
                if line.strip():
                    print(f"[{label}]   {line}")
    else:
        print(f"[{label}] [X] Collection failed with code {proc.returncode}")
        # Print error if any
        if stderr:
            print(f"[{label}] Error: {stderr.decode()[:500]}")

    return proc.returncode


async def main():
    parser = argparse.ArgumentParser(
        description="Run complete MLB collections for 2024 and 2025"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: run with 5 players per collection'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Custom limit for players per collection'
    )
    parser.add_argument(
        '--year',
        type=int,
        choices=[2024, 2025],
        help='Run for specific year only'
    )
    parser.add_argument(
        '--skip-pbp',
        action='store_true',
        help='Skip play-by-play collections'
    )
    parser.add_argument(
        '--skip-pitch',
        action='store_true',
        help='Skip pitch-by-pitch collections'
    )

    args = parser.parse_args()

    # Determine limit
    limit = 5 if args.test else args.limit

    print("="*80)
    print("MLB COLLECTIONS FOR 2024 & 2025")
    print("="*80)
    print(f"Start time: {datetime.now()}")

    if limit:
        print(f"Mode: LIMITED ({limit} players per collection)")
    else:
        print(f"Mode: FULL COLLECTION (ALL PLAYERS)")

    # Check current status
    check_collection_status()

    # Determine which years to process
    years = [args.year] if args.year else [2024, 2025]

    # Build list of collections to run
    collections = []

    for year in years:
        if not args.skip_pbp:
            # Check if PBP script exists for year
            if year == 2025:
                collections.append((f"collect_pbp_{year}.py", year, "PBP", limit))
            elif year == 2024:
                # Check if 2024 PBP script exists
                pbp_2024 = script_dir / f"collect_pbp_{year}.py"
                if not pbp_2024.exists():
                    print(f"[WARNING] No PBP script for {year}, will use pitch collection only")
                else:
                    collections.append((f"collect_pbp_{year}.py", year, "PBP", limit))

        if not args.skip_pitch:
            collections.append((f"collect_pitch_data_{year}.py", year, "Pitch", limit))

    if not collections:
        print("No collections to run!")
        return

    print(f"\nCollections to run: {len(collections)}")
    for script, year, ctype, _ in collections:
        print(f"  - {year} {ctype}: {script}")

    print("\n" + "="*80)
    print("STARTING PARALLEL COLLECTIONS")
    print("="*80)

    start_time = asyncio.get_event_loop().time()

    # Run all collections in parallel
    tasks = [run_collection(script, year, ctype, lim) for script, year, ctype, lim in collections]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = asyncio.get_event_loop().time() - start_time

    # Print results
    print("\n" + "="*80)
    print("COLLECTION RESULTS")
    print("="*80)

    for (script, year, ctype, _), result in zip(collections, results):
        if isinstance(result, Exception):
            print(f"{year} {ctype}: [X] FAILED - {result}")
        elif result == 0:
            print(f"{year} {ctype}: [OK] SUCCESS")
        else:
            print(f"{year} {ctype}: [X] FAILED (exit code {result})")

    # Final status check
    print("\n" + "="*80)
    print("FINAL STATUS")
    print("="*80)
    check_collection_status()

    print("\n" + "="*80)
    print("ALL COLLECTIONS COMPLETE")
    print("="*80)
    print(f"End time: {datetime.now()}")
    print(f"Total time: {elapsed/60:.1f} minutes")

    # Estimate for full collection
    if limit:
        print(f"\nNote: This was a limited run with {limit} players per collection.")
        print("For full collection, expect:")
        print("  - 2025: ~5,700 players (2-3 days)")
        print("  - 2024: ~5,000 players (2-3 days)")
        print("  - Total: 4-6 days if run sequentially, 2-3 days if parallel")

    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())