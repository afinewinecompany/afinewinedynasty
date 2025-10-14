"""
Safely collect Google Trends data for top HYPE leaderboard players.

This script:
1. Fetches top N players from the leaderboard
2. Collects Google Trends data with conservative rate limiting
3. Uses exponential backoff on rate limit errors
4. Skips players with recent data (within 24 hours)
5. Stops gracefully on repeated failures

Usage:
    python collect_leaderboard_trends.py --limit 10
    python collect_leaderboard_trends.py --limit 20 --force  # Ignore recent data
"""

import sys
import time
import argparse
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend
from app.services.google_trends_collector import GoogleTrendsCollector


def get_top_leaderboard_players(db: Session, limit: int = 10):
    """Get top N players from the HYPE leaderboard (prospects only)"""
    players = db.query(PlayerHype).filter(
        PlayerHype.player_type == 'prospect'
    ).order_by(
        desc(PlayerHype.hype_score)
    ).limit(limit).all()

    return players


def has_recent_data(db: Session, player_hype_id: int, hours: int = 24) -> bool:
    """Check if player has trends data collected within last N hours"""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    recent_trend = db.query(SearchTrend).filter(
        SearchTrend.player_hype_id == player_hype_id,
        SearchTrend.collected_at >= cutoff
    ).first()

    return recent_trend is not None


def collect_with_retry(collector: GoogleTrendsCollector, player_name: str,
                       player_hype_id: int, max_retries: int = 3) -> bool:
    """
    Attempt to collect trends data with exponential backoff on rate limits.

    Returns:
        True if successful, False if failed
    """
    base_delay = 30  # Start with 30 second delay

    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}...", end=" ", flush=True)
            success = collector.collect_player_trends(player_name, player_hype_id)

            if success:
                print("SUCCESS")
                return True
            else:
                print("FAILED (no data returned)")
                return False

        except Exception as e:
            error_msg = str(e)

            # Check if it's a rate limit error (429)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"RATE LIMITED - waiting {delay}s before retry...")
                    time.sleep(delay)
                else:
                    print("RATE LIMITED - max retries reached")
                    return False
            else:
                print(f"ERROR: {error_msg}")
                return False

    return False


def main():
    parser = argparse.ArgumentParser(description='Collect Google Trends for top leaderboard players')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of top players to collect (default: 10)')
    parser.add_argument('--force', action='store_true',
                       help='Collect even if recent data exists')
    parser.add_argument('--delay', type=int, default=20,
                       help='Delay between requests in seconds (default: 20)')
    parser.add_argument('--max-failures', type=int, default=3,
                       help='Stop after N consecutive failures (default: 3)')

    args = parser.parse_args()

    print("=" * 70)
    print("GOOGLE TRENDS COLLECTION - TOP LEADERBOARD PLAYERS")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  - Collecting for top {args.limit} players")
    print(f"  - Delay between requests: {args.delay} seconds")
    print(f"  - Force update: {'Yes' if args.force else 'No (skip if data < 24h old)'}")
    print(f"  - Max consecutive failures: {args.max_failures}")
    print()

    db = SyncSessionLocal()
    collector = GoogleTrendsCollector(db)

    try:
        # Get top leaderboard players
        print("Fetching top leaderboard players...")
        players = get_top_leaderboard_players(db, limit=args.limit)
        print(f"Found {len(players)} players\n")

        if not players:
            print("No players found on leaderboard!")
            return

        # Collect trends for each player
        collected = 0
        skipped = 0
        failed = 0
        consecutive_failures = 0

        for idx, player in enumerate(players, 1):
            player_name = player.player_name

            if not player_name:
                print(f"{idx}. {player.player_id} - SKIPPED (no player name)")
                skipped += 1
                continue

            # Check if we have recent data
            if not args.force and has_recent_data(db, player.id):
                print(f"{idx}. {player_name} - SKIPPED (has data < 24h old)")
                skipped += 1
                consecutive_failures = 0  # Reset failure counter on skip
                continue

            print(f"{idx}. {player_name} (HYPE: {player.hype_score:.1f})")

            # Attempt collection with retry
            success = collect_with_retry(collector, player_name, player.id)

            if success:
                collected += 1
                consecutive_failures = 0
                print(f"     Progress: {collected} collected, {skipped} skipped, {failed} failed\n")
            else:
                failed += 1
                consecutive_failures += 1
                print(f"     Progress: {collected} collected, {skipped} skipped, {failed} failed\n")

                # Check if we should stop due to consecutive failures
                if consecutive_failures >= args.max_failures:
                    print(f"STOPPING: {consecutive_failures} consecutive failures reached")
                    print("This likely means Google is blocking requests from your IP.")
                    print("Please wait 30-60 minutes before trying again.")
                    break

            # Delay before next request (except for last player)
            if idx < len(players) and consecutive_failures < args.max_failures:
                print(f"  Waiting {args.delay} seconds before next request...")
                time.sleep(args.delay)

        # Final summary
        print("\n" + "=" * 70)
        print("COLLECTION COMPLETE")
        print("=" * 70)
        print(f"  Collected: {collected}")
        print(f"  Skipped:   {skipped}")
        print(f"  Failed:    {failed}")
        print(f"  Total:     {len(players)}")

        if collected > 0:
            print(f"\nSuccessfully collected trends data for {collected} players!")

        if failed > 0:
            print(f"\nWarning: {failed} collections failed.")
            print("This may be due to Google rate limiting.")
            print("Consider waiting 30-60 minutes before retrying.")

    except KeyboardInterrupt:
        print("\n\nCollection interrupted by user")
        print(f"Partial results: {collected} collected, {skipped} skipped, {failed} failed")

    finally:
        db.close()


if __name__ == "__main__":
    main()
