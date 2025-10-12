"""
Run collection with proper .env loading
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# Load .env file FIRST before any imports
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention
from app.services.social_collector import SocialMediaCollector
from app.services.hype_calculator import HypeCalculator
from sqlalchemy import func

async def collect_for_trey():
    """Focus on collecting for Trey Yesavage with loaded credentials"""

    # Verify credentials are loaded
    print("Checking loaded credentials:")
    print(f"  BLUESKY_HANDLE: {os.getenv('BLUESKY_HANDLE') or 'NOT SET'}")
    print(f"  BLUESKY_APP_PASSWORD: {'SET' if os.getenv('BLUESKY_APP_PASSWORD') else 'NOT SET'}")
    print(f"  TWITTER_BEARER_TOKEN: {'SET' if os.getenv('TWITTER_BEARER_TOKEN') else 'NOT SET'}")
    print(f"  REDDIT_CLIENT_ID: {os.getenv('REDDIT_CLIENT_ID') or 'NOT SET'}")
    print()

    db = SessionLocal()

    try:
        # Find Trey Yesavage
        trey = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%yesavage%')
        ).first()

        if not trey:
            print("ERROR: Trey Yesavage not found")
            return

        print(f"Found: {trey.player_name} (ID: {trey.player_id})")
        print(f"Current HYPE Score: {trey.hype_score}")
        print(f"Current mentions: {trey.total_mentions_24h} (24h), {trey.total_mentions_7d} (7d)")

        # Count existing mentions
        existing_mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == trey.id
        ).count()
        print(f"Existing social mentions: {existing_mentions}")
        print()

        # Collect data
        collector = SocialMediaCollector(db)

        print("="*70)
        print("COLLECTING SOCIAL DATA FOR TREY YESAVAGE...")
        print("="*70)

        result = await collector.collect_all_platforms(
            trey.player_name,
            trey.player_id
        )

        # Show results for each platform
        for platform, data in result.items():
            print(f"\n{platform.upper()}:")
            print(f"  Status: {data.get('status', 'unknown')}")

            if data.get('status') == 'success':
                print(f"  Posts collected: {data.get('count', 0)}")
                if data.get('posts'):
                    print(f"  Sample posts:")
                    for post in data.get('posts', [])[:3]:
                        text = post.get('text', '')[:80]
                        print(f"    - {text}...")
            elif data.get('status') == 'error':
                print(f"  Error: {data.get('message', 'Unknown error')}")
            elif data.get('status') == 'skipped':
                print(f"  Reason: {data.get('reason', 'Unknown')}")

        # Count new mentions
        new_mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == trey.id
        ).count()

        print(f"\n" + "="*70)
        print(f"RESULTS:")
        print(f"  Mentions before: {existing_mentions}")
        print(f"  Mentions after: {new_mentions}")
        print(f"  NEW mentions added: {new_mentions - existing_mentions}")

        # Show breakdown by platform
        platform_counts = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('count')
        ).filter(
            SocialMention.player_hype_id == trey.id
        ).group_by(SocialMention.platform).all()

        print(f"\nMentions by platform:")
        for platform, count in platform_counts:
            print(f"  {platform}: {count}")

        # Specifically look for Bluesky posts
        bluesky_mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == trey.id,
            SocialMention.platform == 'bluesky'
        ).all()

        if bluesky_mentions:
            print(f"\n" + "="*70)
            print(f"BLUESKY POSTS FOR TREY YESAVAGE ({len(bluesky_mentions)} total):")
            print("="*70)
            for i, mention in enumerate(bluesky_mentions[:5], 1):
                print(f"\n{i}. {mention.content[:150]}...")
                print(f"   URL: {mention.url}")
                print(f"   Posted: {mention.posted_at}")
                print(f"   Likes: {mention.likes}, Shares: {mention.shares}")
        else:
            print(f"\nNO Bluesky posts found for Trey Yesavage")

        # Recalculate HYPE score
        print(f"\n" + "="*70)
        print("RECALCULATING HYPE SCORE...")
        print("="*70)

        calculator = HypeCalculator(db)
        calc_result = calculator.calculate_hype_score(trey.player_id)

        print(f"New HYPE Score: {calc_result['hype_score']:.2f}")
        print(f"24h Mentions: {calc_result['metrics']['social'].get('total_mentions_24h', 0)}")
        print(f"7d Mentions: {calc_result['metrics']['social'].get('total_mentions_7d', 0)}")
        print(f"14d Mentions: {calc_result['metrics']['social'].get('total_mentions_14d', 0)}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("COLLECTING WITH LOADED CREDENTIALS")
    print("="*70)
    asyncio.run(collect_for_trey())