#!/usr/bin/env python
"""
Keep system awake during MLB data collection.
Prevents Windows from sleeping while collections are running.

Usage:
    python keep_awake_collector.py --collection-type all
    python keep_awake_collector.py --collection-type pitch --years 2024 2025
"""

import argparse
import asyncio
import subprocess
import sys
import os
import ctypes
from pathlib import Path
from datetime import datetime
import time
import json

# Windows API constants for preventing sleep
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

class KeepAwakeCollector:
    """Manages collections while keeping system awake."""

    def __init__(self):
        self.checkpoints_file = Path("logs/collection_checkpoints.json")
        self.running_processes = []

    def prevent_sleep(self):
        """Prevent Windows from sleeping."""
        if sys.platform == "win32":
            print("Preventing Windows from sleeping...")
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )

    def allow_sleep(self):
        """Allow Windows to sleep again."""
        if sys.platform == "win32":
            print("Allowing Windows to sleep again...")
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    def load_checkpoints(self):
        """Load collection checkpoints."""
        if self.checkpoints_file.exists():
            with open(self.checkpoints_file, 'r') as f:
                return json.load(f)
        return {}

    def save_checkpoint(self, collection_type, year, last_player_id, player_index):
        """Save collection checkpoint for resuming."""
        checkpoints = self.load_checkpoints()

        key = f"{collection_type}_{year}"
        checkpoints[key] = {
            "last_player_id": last_player_id,
            "player_index": player_index,
            "timestamp": datetime.now().isoformat()
        }

        # Ensure logs directory exists
        self.checkpoints_file.parent.mkdir(exist_ok=True)

        with open(self.checkpoints_file, 'w') as f:
            json.dump(checkpoints, f, indent=2)

    def get_resume_point(self, collection_type, year):
        """Get resume point for a collection."""
        checkpoints = self.load_checkpoints()
        key = f"{collection_type}_{year}"

        if key in checkpoints:
            checkpoint = checkpoints[key]
            print(f"Found checkpoint for {key}: Player index {checkpoint['player_index']}")
            return checkpoint['player_index']
        return 0

    async def run_collection_with_resume(self, script_name, year, collection_type):
        """Run collection with resume capability."""
        script_path = Path(__file__).parent / script_name

        # Get resume point
        resume_index = self.get_resume_point(collection_type, year)

        cmd = [sys.executable, str(script_path)]

        # Add offset parameter if resuming
        if resume_index > 0:
            cmd.extend(['--offset', str(resume_index)])
            print(f"Resuming {collection_type} {year} from player {resume_index}")

        log_file = f"logs/{collection_type}_{year}_awake.log"

        print(f"Starting {collection_type} {year} collection...")
        print(f"Command: {' '.join(cmd)}")
        print(f"Log: {log_file}")

        with open(log_file, 'w') as log:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log,
                stderr=asyncio.subprocess.STDOUT
            )
            self.running_processes.append(proc)
            return proc

    async def monitor_and_checkpoint(self, log_file, collection_type, year):
        """Monitor log file and save checkpoints."""
        log_path = Path(log_file)
        last_position = 0

        while True:
            await asyncio.sleep(30)  # Check every 30 seconds

            if log_path.exists():
                with open(log_path, 'r') as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    last_position = f.tell()

                    for line in new_lines:
                        # Look for player processing lines to save checkpoints
                        if "Processing" in line and "ID:" in line:
                            try:
                                # Extract player ID and index
                                if "[" in line and "/" in line:
                                    parts = line.split("[")[1].split("]")[0].split("/")
                                    player_index = int(parts[0])

                                    if "ID:" in line:
                                        player_id = line.split("ID:")[1].split(")")[0].strip()
                                        self.save_checkpoint(collection_type, year, player_id, player_index)
                                        print(f"Checkpoint saved: {collection_type} {year} - Player {player_index}")
                            except Exception as e:
                                pass  # Silent fail on parsing errors

    async def run_all_collections(self, collection_types, years):
        """Run all specified collections with keep-awake."""
        try:
            # Prevent sleep
            self.prevent_sleep()

            tasks = []
            monitor_tasks = []

            # Start collections
            for year in years:
                if 'pitch' in collection_types:
                    script = f"collect_pitch_data_{year}.py"
                    proc_task = self.run_collection_with_resume(script, year, 'pitch')
                    tasks.append(proc_task)

                    log_file = f"logs/pitch_{year}_awake.log"
                    monitor_task = self.monitor_and_checkpoint(log_file, 'pitch', year)
                    monitor_tasks.append(monitor_task)

                if 'pbp' in collection_types:
                    script = f"collect_pbp_{year}.py"
                    proc_task = self.run_collection_with_resume(script, year, 'pbp')
                    tasks.append(proc_task)

                    log_file = f"logs/pbp_{year}_awake.log"
                    monitor_task = self.monitor_and_checkpoint(log_file, 'pbp', year)
                    monitor_tasks.append(monitor_task)

            # Start all processes
            processes = await asyncio.gather(*tasks)

            print(f"\nAll {len(processes)} collections started.")
            print("System will stay awake until collections complete.")
            print("Press Ctrl+C to stop and allow sleep.\n")

            # Run monitoring in background
            monitor_future = asyncio.gather(*monitor_tasks, return_exceptions=True)

            # Wait for all processes to complete
            await asyncio.gather(*[p.wait() for p in processes])

            print("\nAll collections completed!")

        except KeyboardInterrupt:
            print("\n\nStopping collections...")
            for proc in self.running_processes:
                proc.terminate()

        finally:
            # Allow sleep again
            self.allow_sleep()


def main():
    parser = argparse.ArgumentParser(description="Run MLB collections while keeping system awake")
    parser.add_argument(
        '--collection-type',
        choices=['pitch', 'pbp', 'all'],
        default='all',
        help='Type of collection to run'
    )
    parser.add_argument(
        '--years',
        nargs='+',
        type=int,
        default=[2023, 2024, 2025],
        help='Years to collect (default: 2023 2024 2025)'
    )

    args = parser.parse_args()

    print("="*70)
    print("MLB COLLECTION WITH KEEP-AWAKE")
    print("="*70)
    print(f"Collection types: {args.collection_type}")
    print(f"Years: {args.years}")
    print("="*70)

    # Determine collection types
    if args.collection_type == 'all':
        collection_types = ['pitch', 'pbp']
    else:
        collection_types = [args.collection_type]

    collector = KeepAwakeCollector()

    # Run collections
    asyncio.run(collector.run_all_collections(collection_types, args.years))


if __name__ == "__main__":
    main()