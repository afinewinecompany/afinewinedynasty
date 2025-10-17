#!/usr/bin/env python
"""
Master MLB Stats Collection Orchestrator
Runs both play-by-play and pitch-by-pitch collections for hitters and pitchers.

This script ensures all MLB stats are collected properly:
1. Play-by-play data (plate appearances)
2. Pitch-by-pitch data for batters
3. Pitch-by-pitch data for pitchers

Usage:
    python run_complete_mlb_collections.py --test     # Test with 5 players
    python run_complete_mlb_collections.py --small    # Small batch (25 players)
    python run_complete_mlb_collections.py --medium   # Medium batch (100 players)
    python run_complete_mlb_collections.py            # Full collection
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
    """Check current collection status for all tables."""
    print("\n" + "="*80)
    print("CURRENT COLLECTION STATUS")
    print("="*80)

    with sync_engine.connect() as conn:
        # Check play-by-play data
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_pas,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date
            FROM milb_plate_appearances
            WHERE season = 2025
        """))
        row = result.fetchone()

        print("\n1. Play-by-Play (Plate Appearances):")
        print(f"   Total PAs: {row.total_pas:,}")
        print(f"   Unique players: {row.unique_players:,}")
        print(f"   Date range: {row.first_date} to {row.last_date}" if row.first_date else "   No data")

        # Check batter pitch data
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_pitches,
                COUNT(DISTINCT mlb_batter_id) as unique_batters,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date
            FROM milb_batter_pitches
            WHERE season = 2025
        """))
        row = result.fetchone() if result else None

        print("\n2. Batter Pitch-by-Pitch Data:")
        if row:
            print(f"   Total pitches seen: {row.total_pitches:,}")
            print(f"   Unique batters: {row.unique_batters:,}")
            print(f"   Date range: {row.first_date} to {row.last_date}" if row.first_date else "   No data")
        else:
            print("   Table doesn't exist yet")

        # Check pitcher pitch data
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total_pitches,
                COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date
            FROM milb_pitcher_pitches
            WHERE season = 2025
        """))
        row = result.fetchone() if result else None

        print("\n3. Pitcher Pitch-by-Pitch Data:")
        if row:
            print(f"   Total pitches thrown: {row.total_pitches:,}")
            print(f"   Unique pitchers: {row.unique_pitchers:,}")
            print(f"   Date range: {row.first_date} to {row.last_date}" if row.first_date else "   No data")
        else:
            print("   Table doesn't exist yet")


def ensure_tables_exist():
    """Ensure all required tables exist."""
    print("\n" + "="*80)
    print("CHECKING TABLES")
    print("="*80)

    with sync_engine.begin() as conn:
        # Check/create milb_batter_pitches table
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'milb_batter_pitches'
        """))

        if result.scalar() == 0:
            print("Creating milb_batter_pitches table...")
            conn.execute(text("""
                CREATE TABLE milb_batter_pitches (
                    id SERIAL PRIMARY KEY,
                    mlb_batter_id INTEGER NOT NULL,
                    mlb_pitcher_id INTEGER,
                    game_pk BIGINT NOT NULL,
                    game_date DATE,
                    season INTEGER,
                    level VARCHAR(20),
                    at_bat_index INTEGER,
                    pitch_number INTEGER,
                    inning INTEGER,
                    half_inning VARCHAR(10),

                    -- Pitch characteristics
                    pitch_type VARCHAR(10),
                    pitch_type_description VARCHAR(50),
                    start_speed FLOAT,
                    end_speed FLOAT,
                    pfx_x FLOAT,
                    pfx_z FLOAT,

                    -- Release point
                    release_pos_x FLOAT,
                    release_pos_y FLOAT,
                    release_pos_z FLOAT,
                    release_extension FLOAT,

                    -- Spin
                    spin_rate INTEGER,
                    spin_direction INTEGER,

                    -- Location
                    plate_x FLOAT,
                    plate_z FLOAT,
                    zone INTEGER,

                    -- Result
                    pitch_call VARCHAR(100),
                    pitch_result VARCHAR(100),
                    is_strike BOOLEAN,
                    balls INTEGER,
                    strikes INTEGER,
                    outs INTEGER,

                    -- Swing/contact
                    swing BOOLEAN,
                    contact BOOLEAN,
                    swing_and_miss BOOLEAN,
                    foul BOOLEAN,

                    -- PA result (if final pitch)
                    is_final_pitch BOOLEAN,
                    pa_result VARCHAR(50),
                    pa_result_description TEXT,

                    -- Batted ball (if applicable)
                    launch_speed FLOAT,
                    launch_angle FLOAT,
                    total_distance FLOAT,
                    trajectory VARCHAR(20),
                    hardness VARCHAR(20),
                    hit_location INTEGER,
                    coord_x FLOAT,
                    coord_y FLOAT,

                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(mlb_batter_id, game_pk, at_bat_index, pitch_number)
                )
            """))

            # Create indexes
            conn.execute(text("CREATE INDEX idx_batter_pitches_player ON milb_batter_pitches(mlb_batter_id)"))
            conn.execute(text("CREATE INDEX idx_batter_pitches_season ON milb_batter_pitches(season)"))
            conn.execute(text("CREATE INDEX idx_batter_pitches_game ON milb_batter_pitches(game_pk)"))
            print("[OK] Created milb_batter_pitches table")
        else:
            print("[OK] milb_batter_pitches table exists")

        # Check/create milb_pitcher_pitches table
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'milb_pitcher_pitches'
        """))

        if result.scalar() == 0:
            print("Creating milb_pitcher_pitches table...")
            conn.execute(text("""
                CREATE TABLE milb_pitcher_pitches (
                    id SERIAL PRIMARY KEY,
                    mlb_pitcher_id INTEGER NOT NULL,
                    mlb_batter_id INTEGER,
                    game_pk BIGINT NOT NULL,
                    game_date DATE,
                    season INTEGER,
                    level VARCHAR(20),
                    at_bat_index INTEGER,
                    pitch_number INTEGER,
                    inning INTEGER,
                    half_inning VARCHAR(10),

                    -- Pitch characteristics
                    pitch_type VARCHAR(10),
                    pitch_type_description VARCHAR(50),
                    start_speed FLOAT,
                    end_speed FLOAT,
                    pfx_x FLOAT,
                    pfx_z FLOAT,

                    -- Release point
                    release_pos_x FLOAT,
                    release_pos_y FLOAT,
                    release_pos_z FLOAT,
                    release_extension FLOAT,

                    -- Spin
                    spin_rate INTEGER,
                    spin_direction INTEGER,

                    -- Location
                    plate_x FLOAT,
                    plate_z FLOAT,
                    zone INTEGER,

                    -- Result
                    pitch_call VARCHAR(100),
                    pitch_result VARCHAR(100),
                    is_strike BOOLEAN,
                    balls INTEGER,
                    strikes INTEGER,
                    outs INTEGER,

                    -- Swing/contact
                    swing BOOLEAN,
                    contact BOOLEAN,
                    swing_and_miss BOOLEAN,
                    foul BOOLEAN,

                    -- PA result (if final pitch)
                    is_final_pitch BOOLEAN,
                    pa_result VARCHAR(50),
                    pa_result_description TEXT,

                    -- Batted ball (if applicable)
                    launch_speed FLOAT,
                    launch_angle FLOAT,
                    total_distance FLOAT,
                    trajectory VARCHAR(20),
                    hardness VARCHAR(20),
                    hit_location INTEGER,
                    coord_x FLOAT,
                    coord_y FLOAT,

                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(mlb_pitcher_id, game_pk, at_bat_index, pitch_number)
                )
            """))

            # Create indexes
            conn.execute(text("CREATE INDEX idx_pitcher_pitches_player ON milb_pitcher_pitches(mlb_pitcher_id)"))
            conn.execute(text("CREATE INDEX idx_pitcher_pitches_season ON milb_pitcher_pitches(season)"))
            conn.execute(text("CREATE INDEX idx_pitcher_pitches_game ON milb_pitcher_pitches(game_pk)"))
            print("[OK] Created milb_pitcher_pitches table")
        else:
            print("[OK] milb_pitcher_pitches table exists")

        # milb_plate_appearances should already exist from pbp collection
        result = conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'milb_plate_appearances'
        """))

        if result.scalar() > 0:
            print("[OK] milb_plate_appearances table exists")
        else:
            print("[X] milb_plate_appearances table missing - will be created by PBP collector")


async def run_collection_type(collection_type: str, limit: int = None):
    """Run a specific collection type."""
    if collection_type == "pbp":
        script = "collect_pbp_2025.py"
        name = "Play-by-Play"
    elif collection_type == "pitch":
        script = "collect_pitch_data_2025.py"
        name = "Pitch-by-Pitch"
    else:
        raise ValueError(f"Unknown collection type: {collection_type}")

    script_path = script_dir / script

    cmd = [sys.executable, str(script_path)]
    if limit:
        cmd.extend(['--limit', str(limit)])

    print(f"\n[{name}] Starting collection...")
    print(f"[{name}] Command: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )

    # Stream output
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        print(f"[{name}] {line.decode().rstrip()}")

    await proc.wait()

    if proc.returncode == 0:
        print(f"[{name}] [OK] Collection complete!")
    else:
        print(f"[{name}] [X] Collection failed with code {proc.returncode}")

    return proc.returncode


async def main():
    parser = argparse.ArgumentParser(
        description="Master MLB Stats Collection Orchestrator"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: run with 5 players'
    )
    parser.add_argument(
        '--small',
        action='store_true',
        help='Small batch: 25 players'
    )
    parser.add_argument(
        '--medium',
        action='store_true',
        help='Medium batch: 100 players'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Custom limit for players'
    )
    parser.add_argument(
        '--concurrent',
        action='store_true',
        help='Run collections concurrently (faster but more resource intensive)'
    )
    parser.add_argument(
        '--skip-pbp',
        action='store_true',
        help='Skip play-by-play collection'
    )
    parser.add_argument(
        '--skip-pitch',
        action='store_true',
        help='Skip pitch-by-pitch collection'
    )

    args = parser.parse_args()

    # Determine limit
    if args.test:
        limit = 5
    elif args.small:
        limit = 25
    elif args.medium:
        limit = 100
    else:
        limit = args.limit

    print("="*80)
    print("MLB STATS COLLECTION ORCHESTRATOR")
    print("="*80)
    print(f"Start time: {datetime.now()}")

    if limit:
        print(f"Player limit: {limit}")
    else:
        print("Mode: FULL COLLECTION")

    if args.concurrent:
        print("Execution: CONCURRENT (both collections at once)")
    else:
        print("Execution: SEQUENTIAL (one after another)")

    # Ensure tables exist
    ensure_tables_exist()

    # Check current status
    check_collection_status()

    print("\n" + "="*80)
    print("STARTING COLLECTIONS")
    print("="*80)

    start_time = asyncio.get_event_loop().time()

    # Determine which collections to run
    collections = []
    if not args.skip_pbp:
        collections.append(("pbp", "Play-by-Play"))
    if not args.skip_pitch:
        collections.append(("pitch", "Pitch-by-Pitch"))

    if not collections:
        print("No collections selected!")
        return

    # Run collections
    if args.concurrent and len(collections) > 1:
        print("\nRunning collections CONCURRENTLY...")
        tasks = [run_collection_type(ctype, limit) for ctype, _ in collections]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print results
        for (ctype, name), result in zip(collections, results):
            if isinstance(result, Exception):
                print(f"{name}: [X] FAILED - {result}")
            elif result == 0:
                print(f"{name}: [OK] SUCCESS")
            else:
                print(f"{name}: [X] FAILED (exit code {result})")
    else:
        print("\nRunning collections SEQUENTIALLY...")
        for ctype, name in collections:
            print(f"\nStarting {name} collection...")
            result = await run_collection_type(ctype, limit)

            if result != 0:
                print(f"\n{name} collection failed! Stopping.")
                break

    elapsed = asyncio.get_event_loop().time() - start_time

    # Final status check
    print("\n" + "="*80)
    print("FINAL STATUS")
    print("="*80)
    check_collection_status()

    print("\n" + "="*80)
    print("COLLECTION COMPLETE")
    print("="*80)
    print(f"End time: {datetime.now()}")
    print(f"Total time: {elapsed/60:.1f} minutes")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())