"""
Scheduled Google Trends Collection Script
Run this periodically to update trends data for high-priority players

USAGE:
    python scheduled_trends_collection.py --tier 1        # Collect top 20 players (recommended daily)
    python scheduled_trends_collection.py --tier 2        # Collect top 50 players (recommended weekly)
    python scheduled_trends_collection.py --tier 3        # Collect top 100 players (recommended monthly)
    python scheduled_trends_collection.py --all          # Collect all (NOT RECOMMENDED - will be rate limited)
    python scheduled_trends_collection.py --player-id paul-skenes  # Collect specific player
"""
import argparse
import time
from datetime import datetime, timedelta
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend
from app.services.google_trends_collector import GoogleTrendsCollector

# Configuration
TIER_1_LIMIT = 20   # Top 20 - collect daily
TIER_2_LIMIT = 50   # Top 50 - collect weekly
TIER_3_LIMIT = 100  # Top 100 - collect monthly

# Delay between requests (seconds)
# Start conservatively, increase if you get rate limited
DELAY_BETWEEN_REQUESTS = 15  # 15 seconds is safer than 10

def collect_for_tier(tier: int, db):
    """Collect trends for a specific tier"""

    tier_limits = {
        1: TIER_1_LIMIT,
        2: TIER_2_LIMIT,
        3: TIER_3_LIMIT
    }

    limit = tier_limits.get(tier, TIER_1_LIMIT)

    print(f"\n{'='*70}")
    print(f"TIER {tier} COLLECTION - Top {limit} Players")
    print(f"{'='*70}")
    print(f"Delay between requests: {DELAY_BETWEEN_REQUESTS}s")
    print(f"Estimated time: {(limit * DELAY_BETWEEN_REQUESTS) / 60:.1f} minutes\n")

    # Get top players by hype score
    players = db.query(PlayerHype).order_by(
        PlayerHype.hype_score.desc()
    ).limit(limit).all()

    print(f"Found {len(players)} players to collect\n")

    collector = GoogleTrendsCollector(db)
    successful = 0
    failed = 0
    rate_limited = False

    for idx, player in enumerate(players, 1):
        try:
            # Check if we already have recent data (within last 7 days for tier 1, 30 days for others)
            days_threshold = 7 if tier == 1 else 30 if tier == 2 else 90
            cutoff = datetime.utcnow() - timedelta(days=days_threshold)

            existing = db.query(SearchTrend).filter(
                SearchTrend.player_hype_id == player.id,
                SearchTrend.collected_at >= cutoff
            ).first()

            if existing:
                print(f"[{idx}/{len(players)}] {player.player_name} - SKIP (recent data exists)")
                continue

            print(f"[{idx}/{len(players)}] {player.player_name} - Collecting...", end=" ")

            result = collector.collect_player_trends(
                player_name=player.player_name,
                player_hype_id=player.id,
                timeframe='today 1-m',  # Last month
                geo='US'
            )

            if result['search_interest'] > 0:
                print(f"OK (interest: {result['search_interest']:.1f})")
                successful += 1
            else:
                print(f"OK (no data)")
                successful += 1

            # Rate limiting delay (skip on last item)
            if idx < len(players):
                print(f"    Waiting {DELAY_BETWEEN_REQUESTS}s...")
                time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            error_msg = str(e)
            if '429' in error_msg or 'Too Many Requests' in error_msg:
                print(f"RATE LIMITED!")
                rate_limited = True
                break
            else:
                print(f"ERROR: {error_msg}")
                failed += 1

    print(f"\n{'='*70}")
    print(f"COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total attempts: {successful + failed}")

    if rate_limited:
        print(f"\n⚠️ RATE LIMITED by Google!")
        print(f"   - Collected {successful} players before being blocked")
        print(f"   - Wait 30-60 minutes before trying again")
        print(f"   - Consider using a VPN or proxy")

    return successful, failed, rate_limited

def collect_specific_player(player_id: str, db):
    """Collect trends for a specific player"""

    print(f"\n{'='*70}")
    print(f"SINGLE PLAYER COLLECTION: {player_id}")
    print(f"{'='*70}\n")

    player = db.query(PlayerHype).filter(
        PlayerHype.player_id == player_id
    ).first()

    if not player:
        print(f"ERROR: Player '{player_id}' not found in HYPE data")
        return False

    print(f"Player: {player.player_name}")
    print(f"Current Hype Score: {player.hype_score}")
    print(f"\nCollecting Google Trends data...")

    collector = GoogleTrendsCollector(db)

    try:
        result = collector.collect_player_trends(
            player_name=player.player_name,
            player_hype_id=player.id,
            timeframe='today 1-m',
            geo='US'
        )

        print(f"\n✓ Collection successful!")
        print(f"  Search Interest: {result['search_interest']:.1f}")
        print(f"  Growth Rate: {result['search_growth_rate']:+.1f}%")
        print(f"  Regional Interest: {len(result['regional_interest'])} regions")
        print(f"  Related Queries: {len(result['related_queries'])}")

        return True

    except Exception as e:
        print(f"\n✗ Collection failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Collect Google Trends data for players')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3], help='Collection tier (1=top 20, 2=top 50, 3=top 100)')
    parser.add_argument('--all', action='store_true', help='Collect all players (not recommended)')
    parser.add_argument('--player-id', type=str, help='Collect specific player by ID')

    args = parser.parse_args()

    db = SyncSessionLocal()

    try:
        if args.player_id:
            collect_specific_player(args.player_id, db)
        elif args.all:
            print("\n⚠️ WARNING: Collecting ALL players will likely trigger rate limiting!")
            print("   This is NOT recommended. Use tiers instead.")
            response = input("\nContinue anyway? (yes/no): ")
            if response.lower() == 'yes':
                collect_for_tier(3, db)  # Use tier 3 as proxy for "all"
        elif args.tier:
            collect_for_tier(args.tier, db)
        else:
            print("\nNo action specified. Use --help for usage information.")
            print("\nQuick reference:")
            print("  --tier 1     Collect top 20 players (daily)")
            print("  --tier 2     Collect top 50 players (weekly)")
            print("  --tier 3     Collect top 100 players (monthly)")
            print("  --player-id  Collect specific player")

    finally:
        db.close()

if __name__ == '__main__':
    main()
