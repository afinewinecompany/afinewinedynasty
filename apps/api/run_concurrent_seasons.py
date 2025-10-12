"""
Run multiple season collections concurrently in separate background processes.
Each season runs independently with its own log file.
"""

import subprocess
import sys
import time
from datetime import datetime


def start_season_collection(season: int, levels: list) -> dict:
    """Start collection for a single season in background."""
    log_file = f'collection_{season}.log'

    cmd = [
        sys.executable, '-m', 'scripts.collect_all_milb_gamelog',
        '--season', str(season),
        '--levels', *levels
    ]

    print(f"Starting {season} season collection...")
    print(f"  Levels: {', '.join(levels)}")
    print(f"  Log file: {log_file}")

    # Start process in background, redirect output to log file
    process = subprocess.Popen(
        cmd,
        cwd='.',
        stdout=open(log_file, 'w'),
        stderr=subprocess.STDOUT,
        text=True
    )

    return {
        'season': season,
        'process': process,
        'log_file': log_file,
        'start_time': datetime.now()
    }


def main():
    """Start concurrent collections for multiple seasons."""
    print("\n" + "=" * 80)
    print("MiLB Game Log Collection - Concurrent Multi-Season Run")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    # 2024 is already running with AAA, AA, A+ - don't restart it
    # Start 2023, 2022, 2021 with all levels
    seasons_to_start = [
        {'season': 2023, 'levels': ['AAA', 'AA', 'A+', 'A', 'DSL', 'ROK', 'ACL']},
        {'season': 2022, 'levels': ['AAA', 'AA', 'A+', 'A', 'DSL', 'ROK', 'ACL']},
        {'season': 2021, 'levels': ['AAA', 'AA', 'A+', 'A', 'DSL', 'ROK', 'ACL']},
    ]

    processes = []

    for config in seasons_to_start:
        proc_info = start_season_collection(config['season'], config['levels'])
        processes.append(proc_info)
        time.sleep(2)  # Stagger starts by 2 seconds
        print()

    print("=" * 80)
    print("All seasons started!")
    print("=" * 80)
    print("\nActive collections:")
    print("  - 2024: collection_batch.log (already running - AAA, AA, A+ only)")
    for p in processes:
        print(f"  - {p['season']}: {p['log_file']} (PID: {p['process'].pid})")

    print("\nMonitor progress with:")
    print("  tail -f collection_2023.log")
    print("  tail -f collection_2022.log")
    print("  tail -f collection_2021.log")
    print("\nProcesses will run in background. Check logs for progress.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
