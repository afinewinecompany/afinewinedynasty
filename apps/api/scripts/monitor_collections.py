#!/usr/bin/env python
"""
Monitor running MLB data collections.
Shows real-time progress of all collection processes.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from sqlalchemy import text

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

# Change to API directory
os.chdir(api_dir)

from app.db.database import sync_engine


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_collection_stats():
    """Get current collection statistics."""
    stats = {}

    with sync_engine.connect() as conn:
        for year in [2024, 2025]:
            year_stats = {}

            # Total players with games
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT mlb_player_id)
                FROM milb_game_logs
                WHERE season = :year AND mlb_player_id IS NOT NULL
            """), {"year": year})
            year_stats['total_players'] = result.scalar() or 0

            # Play-by-play stats
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT mlb_player_id) as players,
                    COUNT(*) as total_pas,
                    MAX(created_at) as last_update
                FROM milb_plate_appearances
                WHERE season = :year
            """), {"year": year})
            row = result.fetchone()
            year_stats['pbp_players'] = row.players or 0
            year_stats['pbp_total'] = row.total_pas or 0
            year_stats['pbp_last_update'] = row.last_update

            # Batter pitch stats
            try:
                result = conn.execute(text("""
                    SELECT
                        COUNT(DISTINCT mlb_batter_id) as players,
                        COUNT(*) as total_pitches,
                        MAX(created_at) as last_update
                    FROM milb_batter_pitches
                    WHERE season = :year
                """), {"year": year})
                row = result.fetchone()
                year_stats['batter_players'] = row.players or 0
                year_stats['batter_pitches'] = row.total_pitches or 0
                year_stats['batter_last_update'] = row.last_update
            except:
                year_stats['batter_players'] = 0
                year_stats['batter_pitches'] = 0
                year_stats['batter_last_update'] = None

            # Pitcher pitch stats
            try:
                result = conn.execute(text("""
                    SELECT
                        COUNT(DISTINCT mlb_pitcher_id) as players,
                        COUNT(*) as total_pitches,
                        MAX(created_at) as last_update
                    FROM milb_pitcher_pitches
                    WHERE season = :year
                """), {"year": year})
                row = result.fetchone()
                year_stats['pitcher_players'] = row.players or 0
                year_stats['pitcher_pitches'] = row.total_pitches or 0
                year_stats['pitcher_last_update'] = row.last_update
            except:
                year_stats['pitcher_players'] = 0
                year_stats['pitcher_pitches'] = 0
                year_stats['pitcher_last_update'] = None

            stats[year] = year_stats

    return stats


def check_log_files():
    """Check if log files are being written to."""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir()

    log_status = {}
    for log_file in ["pitch_2024.log", "pitch_2025.log", "pbp_2024.log"]:
        log_path = logs_dir / log_file
        if log_path.exists():
            size = log_path.stat().st_size
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            # Get last line if file is not too large
            if size < 1000000:  # Less than 1MB
                try:
                    with open(log_path, 'r') as f:
                        lines = f.readlines()
                        last_line = lines[-1].strip() if lines else ""
                except:
                    last_line = ""
            else:
                last_line = f"File too large ({size/1024/1024:.1f} MB)"

            log_status[log_file] = {
                'exists': True,
                'size': size,
                'modified': mtime,
                'last_line': last_line[:100]  # Truncate long lines
            }
        else:
            log_status[log_file] = {'exists': False}

    return log_status


def format_time_ago(dt):
    """Format datetime as time ago."""
    if not dt:
        return "Never"

    now = datetime.now()
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds/60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds/3600)}h ago"
    else:
        return f"{int(seconds/86400)}d ago"


def main():
    """Main monitoring loop."""
    print("MLB Collection Monitor")
    print("Press Ctrl+C to exit")
    print("-" * 80)

    try:
        while True:
            clear_screen()

            print("="*80)
            print(f"MLB COLLECTION MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80)

            # Get stats
            stats = get_collection_stats()
            log_status = check_log_files()

            # Display stats for each year
            for year in [2024, 2025]:
                year_stats = stats[year]
                total = year_stats['total_players']

                print(f"\n--- {year} SEASON ---")
                print(f"Total players with games: {total:,}")
                print()

                # PBP Collection
                pbp_players = year_stats['pbp_players']
                pbp_pct = (pbp_players / total * 100) if total > 0 else 0
                pbp_update = format_time_ago(year_stats['pbp_last_update'])
                print(f"Play-by-Play Collection:")
                print(f"  Players: {pbp_players:,}/{total:,} ({pbp_pct:.1f}%)")
                print(f"  Total PAs: {year_stats['pbp_total']:,}")
                print(f"  Last update: {pbp_update}")

                # Batter Pitch Collection
                batter_players = year_stats['batter_players']
                batter_pct = (batter_players / total * 100) if total > 0 else 0
                batter_update = format_time_ago(year_stats['batter_last_update'])
                print(f"\nBatter Pitch-by-Pitch:")
                print(f"  Players: {batter_players:,}/{total:,} ({batter_pct:.1f}%)")
                print(f"  Total pitches: {year_stats['batter_pitches']:,}")
                print(f"  Last update: {batter_update}")

                # Pitcher Pitch Collection
                pitcher_players = year_stats['pitcher_players']
                pitcher_pct = (pitcher_players / total * 100) if total > 0 else 0
                pitcher_update = format_time_ago(year_stats['pitcher_last_update'])
                print(f"\nPitcher Pitch-by-Pitch:")
                print(f"  Players: {pitcher_players:,}/{total:,} ({pitcher_pct:.1f}%)")
                print(f"  Total pitches: {year_stats['pitcher_pitches']:,}")
                print(f"  Last update: {pitcher_update}")

            # Log file status
            print("\n" + "="*80)
            print("LOG FILES")
            print("="*80)
            for log_name, status in log_status.items():
                if status['exists']:
                    size_mb = status['size'] / 1024 / 1024
                    modified = format_time_ago(status['modified'])
                    print(f"{log_name}: {size_mb:.2f} MB, modified {modified}")
                    if status.get('last_line'):
                        print(f"  Last: {status['last_line']}")
                else:
                    print(f"{log_name}: Not found")

            # Estimate time remaining
            print("\n" + "="*80)
            print("ESTIMATES")
            print("="*80)

            # Calculate rates
            for year in [2024, 2025]:
                year_stats = stats[year]

                # Pitch collection rate
                if year_stats['batter_last_update']:
                    time_delta = datetime.now() - year_stats['batter_last_update'].replace(tzinfo=None)
                    hours = time_delta.total_seconds() / 3600
                    if hours > 0 and year_stats['batter_players'] > 0:
                        rate = year_stats['batter_players'] / hours
                        remaining = year_stats['total_players'] - year_stats['batter_players']
                        eta_hours = remaining / rate if rate > 0 else 0
                        print(f"{year} Pitch collection: {rate:.1f} players/hour, ETA: {eta_hours:.1f} hours")

            print("\n" + "="*80)
            print("Refreshing in 30 seconds... (Press Ctrl+C to exit)")

            time.sleep(30)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())