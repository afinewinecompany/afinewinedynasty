#!/usr/bin/env python3
"""
Real-time monitoring dashboard for pitch data collection.
Run this to get a live view of collection status and identify gaps.
"""

import psycopg2
from datetime import datetime, timedelta
import time
import os
import sys

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

class PitchDataMonitor:
    def __init__(self):
        self.conn = psycopg2.connect(DB_URL)
        self.last_check_time = datetime.now()

    def clear_screen(self):
        """Clear console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_overall_status(self):
        """Get overall collection status"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                ROUND((COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk)) * 100, 2) as coverage_pct,
                COUNT(bp.*) as total_pitches
            FROM milb_game_logs gl
            LEFT JOIN milb_batter_pitches bp ON gl.game_pk = bp.game_pk
            WHERE gl.season = 2025
        """)
        return cur.fetchone()

    def get_recent_activity(self, minutes=5):
        """Get recent collection activity"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) as new_pitches,
                COUNT(DISTINCT mlb_batter_id) as players_updated,
                COUNT(DISTINCT game_pk) as games_updated
            FROM milb_batter_pitches
            WHERE created_at > NOW() - INTERVAL %s
        """, (f'{minutes} minutes',))
        return cur.fetchone()

    def get_active_gaps(self):
        """Get players with most missing data"""
        cur = self.conn.cursor()
        cur.execute("""
            WITH gaps AS (
                SELECT
                    p.name,
                    p.position,
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games
                FROM prospects p
                JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
                LEFT JOIN milb_batter_pitches bp ON gl.game_pk = bp.game_pk
                    AND p.mlb_player_id::integer = bp.mlb_batter_id
                WHERE gl.season = 2025
                    AND p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF')
                GROUP BY p.name, p.position
                HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
            )
            SELECT * FROM gaps
            ORDER BY missing_games DESC
            LIMIT 10
        """)
        return cur.fetchall()

    def get_collection_rate(self):
        """Calculate collection rate"""
        cur = self.conn.cursor()

        # Get counts from 1 hour ago and now
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM milb_batter_pitches WHERE created_at < NOW() - INTERVAL '1 hour') as hour_ago,
                (SELECT COUNT(*) FROM milb_batter_pitches) as now
        """)
        result = cur.fetchone()

        if result and result[0]:
            rate = (result[1] - result[0]) / 3600  # pitches per second
            return rate
        return 0

    def display_dashboard(self):
        """Display the monitoring dashboard"""
        self.clear_screen()

        print("=" * 80)
        print("PITCH DATA COLLECTION MONITORING DASHBOARD")
        print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Overall status
        overall = self.get_overall_status()
        print("\nOVERALL STATUS (2025 Season):")
        print("-" * 40)
        print(f"  Total Games: {overall[0]:,}")
        print(f"  Games with Pitch Data: {overall[1]:,}")
        print(f"  Coverage: {overall[2]:.2f}%")
        print(f"  Total Pitches: {overall[3]:,}")

        # Progress bar
        coverage = overall[2]
        bar_length = int(coverage / 2)
        progress_bar = "=" * bar_length + "-" * (50 - bar_length)
        print(f"  Progress: [{progress_bar}]")

        # Recent activity
        recent = self.get_recent_activity(5)
        print("\nRECENT ACTIVITY (Last 5 minutes):")
        print("-" * 40)
        if recent[0] > 0:
            print(f"  New Pitches: {recent[0]:,}")
            print(f"  Players Updated: {recent[1]}")
            print(f"  Games Updated: {recent[2]}")
        else:
            print("  No collection activity detected")

        # Collection rate
        rate = self.get_collection_rate()
        if rate > 0:
            print(f"\nCOLLECTION RATE:")
            print("-" * 40)
            print(f"  Current Rate: {rate:.1f} pitches/second")
            print(f"  Hourly Rate: {int(rate * 3600):,} pitches/hour")

        # Top gaps
        gaps = self.get_active_gaps()
        if gaps:
            print("\nTOP PRIORITY GAPS:")
            print("-" * 40)
            print(f"{'Player':<25} {'Pos':<5} {'Missing':<10} {'Coverage'}")
            for gap in gaps:
                name, pos, total, with_pitch, missing = gap
                coverage_pct = (with_pitch / total * 100) if total > 0 else 0
                print(f"{name:<25} {pos:<5} {missing:<10} {coverage_pct:>6.1f}%")

        print("\n" + "=" * 80)
        print("Press Ctrl+C to exit | Auto-refresh every 30 seconds")

    def run_monitor(self, refresh_interval=30):
        """Run the monitoring loop"""
        try:
            while True:
                self.display_dashboard()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            self.conn.close()
            sys.exit(0)


def main():
    monitor = PitchDataMonitor()
    monitor.run_monitor()


if __name__ == "__main__":
    main()