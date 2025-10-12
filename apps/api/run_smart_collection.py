"""
Smart collection script that handles rate limits gracefully
Focuses on available platforms and implements proper delays
"""
import sys
import os
import asyncio
from dotenv import load_dotenv
import time

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Load .env file FIRST
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention, MediaArticle
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator
from app.services.rss_collector import collect_rss_feeds
from sqlalchemy import func

# Track rate limit status
RATE_LIMIT_STATUS = {
    'twitter': {'limited': False, 'reset_time': None},
    'bluesky': {'limited': False, 'reset_time': None},
    'reddit': {'limited': False, 'reset_time': None}
}

async def collect_with_rate_limit_handling(collector, player_name, player_id):
    """Collect data with intelligent rate limit handling"""
    results = {}

    # Try Reddit first (usually has higher limits)
    if not RATE_LIMIT_STATUS['reddit']['limited']:
        try:
            reddit_result = await collector.collect_reddit(player_name, player_id)
            results['reddit'] = reddit_result
            if reddit_result.get('status') == 'rate_limited':
                RATE_LIMIT_STATUS['reddit']['limited'] = True
                RATE_LIMIT_STATUS['reddit']['reset_time'] = datetime.now() + timedelta(hours=1)
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                RATE_LIMIT_STATUS['reddit']['limited'] = True
            results['reddit'] = {'status': 'error', 'error': str(e)}

    # Try Bluesky if not limited
    if not RATE_LIMIT_STATUS['bluesky']['limited']:
        try:
            bluesky_result = await collector.collect_bluesky(player_name, player_id)
            results['bluesky'] = bluesky_result
            if bluesky_result.get('status') == 'rate_limited' or 'RateLimitExceeded' in str(bluesky_result.get('error', '')):
                RATE_LIMIT_STATUS['bluesky']['limited'] = True
                RATE_LIMIT_STATUS['bluesky']['reset_time'] = datetime.now() + timedelta(hours=24)
        except Exception as e:
            if 'RateLimitExceeded' in str(e) or '429' in str(e):
                RATE_LIMIT_STATUS['bluesky']['limited'] = True
            results['bluesky'] = {'status': 'error', 'error': str(e)}

    # Try Twitter if not limited (but we know it's heavily limited)
    if not RATE_LIMIT_STATUS['twitter']['limited']:
        try:
            twitter_result = await collector.collect_twitter(player_name, player_id)
            results['twitter'] = twitter_result
            if twitter_result.get('status') == 'rate_limited':
                RATE_LIMIT_STATUS['twitter']['limited'] = True
                RATE_LIMIT_STATUS['twitter']['reset_time'] = datetime.now() + timedelta(minutes=15)
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                RATE_LIMIT_STATUS['twitter']['limited'] = True
            results['twitter'] = {'status': 'error', 'error': str(e)}

    return results

async def run_smart_collection():
    """Run collection with rate limit awareness"""

    print("SMART COLLECTION WITH RATE LIMIT HANDLING")
    print("="*80)
    print(f"Time: {datetime.now()}")

    # Verify credentials
    print("\nCredentials loaded:")
    print(f"  BLUESKY: {'YES' if os.getenv('BLUESKY_HANDLE') else 'NO'}")
    print(f"  TWITTER: {'YES' if os.getenv('TWITTER_BEARER_TOKEN') else 'NO'}")
    print(f"  REDDIT: {'YES' if os.getenv('REDDIT_CLIENT_ID') else 'NO'}")
    print()

    db = SessionLocal()

    try:
        # First, collect RSS feeds (no rate limits)
        print("Phase 1: Collecting RSS feeds...")
        print("-"*40)
        rss_results = await collect_rss_feeds(db)
        print(f"RSS Collection complete: {rss_results}")
        print()

        # Get ALL players
        all_players = db.query(PlayerHype).all()
        print(f"Phase 2: Social collection for {len(all_players)} players")
        print("-"*40)

        # Track initial stats
        initial_mentions = db.query(SocialMention).count()
        initial_articles = db.query(MediaArticle).count()

        collector = SocialMediaCollector(db)

        # Statistics
        platform_stats = {'twitter': 0, 'reddit': 0, 'bluesky': 0}
        success_count = 0
        error_count = 0

        # Process one by one with delays to avoid rate limits
        for i, player in enumerate(all_players, 1):
            # Check rate limit status
            platforms_available = []
            for platform, status in RATE_LIMIT_STATUS.items():
                if not status['limited']:
                    platforms_available.append(platform)
                elif status['reset_time'] and datetime.now() > status['reset_time']:
                    # Reset the limit if enough time has passed
                    status['limited'] = False
                    status['reset_time'] = None
                    platforms_available.append(platform)

            if not platforms_available:
                print(f"\nWARNING:  All platforms rate limited. Waiting 60 seconds...")
                await asyncio.sleep(60)
                # Reset Reddit (usually recovers fastest)
                RATE_LIMIT_STATUS['reddit']['limited'] = False
                platforms_available = ['reddit']

            print(f"\n[{i}/{len(all_players)}] {player.player_name}")
            print(f"  Available platforms: {', '.join(platforms_available)}")

            try:
                results = await collect_with_rate_limit_handling(collector, player.player_name, player.player_id)

                # Process results
                had_success = False
                for platform, data in results.items():
                    if data.get('status') == 'success' and data.get('count', 0) > 0:
                        platform_stats[platform] += data['count']
                        print(f"  SUCCESS: {platform}: {data['count']} mentions")
                        had_success = True
                    elif data.get('status') == 'rate_limited':
                        print(f"  WARNING:  {platform}: rate limited")
                    elif data.get('error'):
                        if 'RateLimitExceeded' in str(data['error']) or '429' in str(data['error']):
                            print(f"  WARNING:  {platform}: rate limited")
                        else:
                            print(f"  ERROR: {platform}: error")

                if had_success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                print(f"  ERROR: ERROR: {str(e)[:50]}")
                error_count += 1

            # Intelligent delay based on rate limit status
            active_platforms = len([p for p, s in RATE_LIMIT_STATUS.items() if not s['limited']])
            if active_platforms == 3:
                await asyncio.sleep(0.5)  # All platforms working, minimal delay
            elif active_platforms == 2:
                await asyncio.sleep(1)    # One platform limited, small delay
            elif active_platforms == 1:
                await asyncio.sleep(2)    # Two platforms limited, longer delay
            else:
                await asyncio.sleep(5)    # All limited, wait longer

            # Progress update every 10 players
            if i % 10 == 0:
                print(f"\nProgress: {i}/{len(all_players)} players processed")
                print(f"Mentions collected so far: Twitter={platform_stats['twitter']}, "
                      f"Reddit={platform_stats['reddit']}, Bluesky={platform_stats['bluesky']}")

        print("\n" + "="*80)
        print("Phase 3: Calculating HYPE scores...")
        print("-"*40)

        # Calculate HYPE scores for all players
        calculator = HypeCalculator(db)
        calc_success = 0
        calc_errors = 0

        for i, player in enumerate(all_players, 1):
            try:
                calculator.calculate_hype_score(player.player_id)
                calc_success += 1
                if i % 20 == 0:
                    print(f"  Calculated {i}/{len(all_players)} HYPE scores...")
            except Exception as e:
                calc_errors += 1
                print(f"  Error calculating score for {player.player_name}: {e}")

        # Get final stats
        final_mentions = db.query(SocialMention).count()
        final_articles = db.query(MediaArticle).count()

        # Get platform breakdown
        platform_counts = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('count')
        ).group_by(SocialMention.platform).all()

        print("\n" + "="*80)
        print("FINAL RESULTS")
        print("="*80)

        print(f"\nCollection Statistics:")
        print(f"  Players processed: {len(all_players)}")
        print(f"  Successful collections: {success_count}")
        print(f"  Failed collections: {error_count}")

        print(f"\nNew Data Collected:")
        print(f"  Twitter mentions: {platform_stats['twitter']}")
        print(f"  Reddit mentions: {platform_stats['reddit']}")
        print(f"  Bluesky mentions: {platform_stats['bluesky']}")
        print(f"  RSS articles: {final_articles - initial_articles}")

        print(f"\nTotal in Database:")
        print(f"  Social mentions: {initial_mentions} → {final_mentions} (+{final_mentions - initial_mentions})")
        print(f"  Media articles: {initial_articles} → {final_articles} (+{final_articles - initial_articles})")

        print(f"\nBreakdown by Platform:")
        for platform, count in platform_counts:
            print(f"  {platform}: {count} total mentions")

        print(f"\nHYPE Score Calculations:")
        print(f"  Success: {calc_success}/{len(all_players)}")
        if calc_errors > 0:
            print(f"  Errors: {calc_errors}")

        # Show top 10 players
        print("\n" + "="*80)
        print("TOP 10 BY HYPE SCORE")
        print("="*80)

        top_players = db.query(PlayerHype).order_by(
            PlayerHype.hype_score.desc()
        ).limit(10).all()

        for i, player in enumerate(top_players, 1):
            print(f"{i:2}. {player.player_name:25} | Score: {player.hype_score:6.2f} | "
                  f"24h: {player.total_mentions_24h:4} | "
                  f"7d: {player.total_mentions_7d:4} | "
                  f"14d: {player.total_mentions_14d:4}")

        # Check specific players
        print("\n" + "="*80)
        print("SPECIFIC PLAYER CHECKS")
        print("="*80)

        check_names = ['Trey Yesavage', 'Hagen Smith', 'Cooper Ingle', 'Chase Burns', 'Jac Caglianone']
        for name in check_names:
            player = db.query(PlayerHype).filter(
                PlayerHype.player_name.ilike(f'%{name}%')
            ).first()
            if player:
                # Get mention counts by platform
                platform_breakdown = db.query(
                    SocialMention.platform,
                    func.count(SocialMention.id).label('count')
                ).filter(
                    SocialMention.player_hype_id == player.id
                ).group_by(SocialMention.platform).all()

                platform_str = ", ".join([f"{p}={c}" for p, c in platform_breakdown])
                print(f"{player.player_name:20} - Score: {player.hype_score:6.2f}, Mentions: {platform_str if platform_str else 'none'}")

        print("\n" + "="*80)
        print("COLLECTION COMPLETE")
        print("="*80)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("SMART COLLECTION SYSTEM")
    print("="*80)
    print("This script handles rate limits intelligently:")
    print("- Collects RSS feeds first (no rate limits)")
    print("- Tracks rate limit status per platform")
    print("- Skips rate-limited platforms temporarily")
    print("- Implements smart delays based on platform availability")
    print("="*80)
    print()

    asyncio.run(run_smart_collection())