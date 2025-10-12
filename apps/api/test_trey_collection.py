"""
Test social collection for Trey Yesavage to verify multi-player mention linking
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention
from app.services.social_collector import SocialMediaCollector

async def test_trey_collection():
    """Test collecting data for Trey Yesavage"""
    db = SessionLocal()

    try:
        # Find Trey Yesavage
        trey = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%yesavage%')
        ).first()

        if not trey:
            print("ERROR: Trey Yesavage not found")
            return

        print(f"Found: {trey.player_name} ({trey.player_id})")
        print(f"Current mentions: {db.query(SocialMention).filter(SocialMention.player_hype_id == trey.id).count()}")
        print()

        # Collect Bluesky data
        collector = SocialMediaCollector(db)

        print("Collecting Bluesky data...")
        result = await collector.collect_bluesky_data(trey.player_name, trey.player_id)

        print(f"Result: {result['status']}")
        if result['status'] == 'success':
            print(f"Posts collected: {result['count']}")
        elif result['status'] == 'error':
            print(f"Error: {result.get('message', 'Unknown error')}")

        # Check new mention count
        new_count = db.query(SocialMention).filter(
            SocialMention.player_hype_id == trey.id
        ).count()

        print(f"New mention count: {new_count}")

        # Show recent Bluesky mentions
        bluesky_mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == trey.id,
            SocialMention.platform == 'bluesky'
        ).all()

        print(f"\nBluesky mentions for {trey.player_name}: {len(bluesky_mentions)}")
        for mention in bluesky_mentions[:5]:
            print(f"  - {mention.content[:80]}...")
            print(f"    URL: {mention.url}")
            print()

        # Now check if any posts mention multiple players
        print("\n" + "="*80)
        print("Checking for multi-player posts...")
        print("="*80)

        # Find posts that are linked to multiple players
        from sqlalchemy import func
        multi_player_posts = db.query(
            SocialMention.post_id,
            func.count(SocialMention.player_hype_id).label('player_count')
        ).group_by(
            SocialMention.post_id
        ).having(
            func.count(SocialMention.player_hype_id) > 1
        ).all()

        print(f"\nPosts mentioning multiple players: {len(multi_player_posts)}")

        if multi_player_posts:
            for post_id, count in multi_player_posts[:5]:
                print(f"\n  Post ID: {post_id} - mentions {count} players")
                mentions = db.query(SocialMention).filter(
                    SocialMention.post_id == post_id
                ).all()

                for m in mentions:
                    player = db.query(PlayerHype).filter(PlayerHype.id == m.player_hype_id).first()
                    print(f"    - {player.player_name if player else 'Unknown'}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_trey_collection())
