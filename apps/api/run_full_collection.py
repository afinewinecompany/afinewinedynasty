"""
Run FULL collection for ALL 100 players with loaded credentials
This simulates the hourly scheduler task
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator
from sqlalchemy import func

async def run_full_collection():
    """Run collection for all 100 players"""

    # Verify credentials
    print("Credentials loaded:")
    print(f"  BLUESKY: {'YES' if os.getenv('BLUESKY_HANDLE') else 'NO'}")
    print(f"  TWITTER: {'YES' if os.getenv('TWITTER_BEARER_TOKEN') else 'NO'}")
    print(f"  REDDIT: {'YES' if os.getenv('REDDIT_CLIENT_ID') else 'NO'}")
    print()

    db = SessionLocal()

    try:
        # Get ALL players
        all_players = db.query(PlayerHype).all()
        print(f"Starting collection for {len(all_players)} players")
        print(f"Time: {datetime.utcnow()}")
        print("="*80)

        # Track initial stats
        initial_mentions = db.query(SocialMention).count()
        initial_bluesky = db.query(SocialMention).filter(
            SocialMention.platform == 'bluesky'
        ).count()

        collector = SocialMediaCollector(db)

        # Statistics
        platform_stats = {'twitter': 0, 'reddit': 0, 'bluesky': 0}
        success_count = 0
        error_count = 0

        # Process in batches
        batch_size = 10
        for batch_num in range(0, len(all_players), batch_size):
            batch = all_players[batch_num:batch_num+batch_size]
            print(f"\nBatch {batch_num//batch_size + 1}/{(len(all_players) + batch_size - 1)//batch_size}: ", end="")
            player_names = [p.player_name.split()[-1] for p in batch]  # Last names for brevity
            print(", ".join(player_names))

            tasks = []
            for player in batch:
                tasks.append(
                    collector.collect_all_platforms(
                        player.player_name,
                        player.player_id
                    )
                )

            # Run batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for player, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"  X {player.player_name}: {str(result)[:50]}")
                    error_count += 1
                else:
                    success_count += 1
                    # Track successful collections by platform
                    for platform, data in result.items():
                        if data.get('status') == 'success' and data.get('count', 0) > 0:
                            platform_stats[platform] += data['count']
                            print(f"  + {player.player_name}: {platform}={data['count']}", end=" ")
                    print()  # New line after each player

            # Small delay between batches
            await asyncio.sleep(1)

        print("\n" + "="*80)
        print("COLLECTION PHASE COMPLETE - Now calculating HYPE scores...")
        print("="*80)

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

        # Get final stats
        final_mentions = db.query(SocialMention).count()
        final_bluesky = db.query(SocialMention).filter(
            SocialMention.platform == 'bluesky'
        ).count()

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
        print(f"  Successful: {success_count}")
        print(f"  Errors: {error_count}")

        print(f"\nNew Posts Collected:")
        for platform, count in platform_stats.items():
            if count > 0:
                print(f"  {platform}: {count}")

        print(f"\nTotal Mentions in Database:")
        print(f"  Before: {initial_mentions}")
        print(f"  After: {final_mentions}")
        print(f"  NEW: +{final_mentions - initial_mentions}")

        print(f"\nBluesky Posts:")
        print(f"  Before: {initial_bluesky}")
        print(f"  After: {final_bluesky}")
        print(f"  NEW: +{final_bluesky - initial_bluesky}")

        print(f"\nBreakdown by Platform:")
        for platform, count in platform_counts:
            print(f"  {platform}: {count}")

        print(f"\nHYPE Score Calculations:")
        print(f"  Success: {calc_success}/{len(all_players)}")
        if calc_errors > 0:
            print(f"  Errors: {calc_errors}")

        # Show top 10 players
        print("\n" + "="*80)
        print("TOP 10 BY HYPE SCORE (After Collection)")
        print("="*80)

        top_players = db.query(PlayerHype).order_by(
            PlayerHype.hype_score.desc()
        ).limit(10).all()

        for i, player in enumerate(top_players, 1):
            print(f"{i:2}. {player.player_name:25} | Score: {player.hype_score:6.2f} | 24h: {player.total_mentions_24h:4} | 7d: {player.total_mentions_7d:4} | 14d: {player.total_mentions_14d:4}")

        # Check some specific players
        print("\n" + "="*80)
        print("SAMPLE PLAYER CHECKS")
        print("="*80)

        sample_names = ['Trey Yesavage', 'Hagen Smith', 'Cooper Ingle']
        for name in sample_names:
            player = db.query(PlayerHype).filter(
                PlayerHype.player_name.ilike(f'%{name}%')
            ).first()
            if player:
                bluesky_count = db.query(SocialMention).filter(
                    SocialMention.player_hype_id == player.id,
                    SocialMention.platform == 'bluesky'
                ).count()
                print(f"{player.player_name:20} - Score: {player.hype_score:6.2f}, Bluesky posts: {bluesky_count}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("FULL COLLECTION FOR ALL 100 PLAYERS")
    print("="*80)
    print("This will collect from Twitter, Reddit, and Bluesky")
    print("Expected time: 5-10 minutes")
    print("="*80)
    print()

    asyncio.run(run_full_collection())