"""
Check Trey Yesavage's data and Bluesky collection status
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention

def check_trey():
    """Check Trey Yesavage's data"""
    db = SessionLocal()

    try:
        # Find Trey Yesavage
        player = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%yesavage%')
        ).first()

        if not player:
            print("ERROR: Trey Yesavage not found in PlayerHype table")
            print("\nSearching for similar names:")
            players = db.query(PlayerHype).all()
            for p in players[:10]:
                print(f"  - {p.player_name} ({p.player_id})")
            return

        print(f"Found: {player.player_name}")
        print(f"Player ID: {player.player_id}")
        print(f"HYPE Score: {player.hype_score}")
        print(f"24h Mentions: {player.total_mentions_24h}")
        print(f"7d Mentions: {player.total_mentions_7d}")
        print(f"14d Mentions: {player.total_mentions_14d}")
        print(f"Last Calculated: {player.last_calculated}")
        print()

        # Check social mentions
        mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id
        ).all()

        print(f"Total Social Mentions in DB: {len(mentions)}")

        # Break down by platform
        by_platform = {}
        for mention in mentions:
            if mention.platform not in by_platform:
                by_platform[mention.platform] = []
            by_platform[mention.platform].append(mention)

        for platform, platform_mentions in by_platform.items():
            print(f"\n{platform.upper()}: {len(platform_mentions)} mentions")
            for mention in platform_mentions[:3]:
                print(f"  - {mention.content[:80]}...")
                print(f"    Posted: {mention.posted_at}")

        # Check all Bluesky mentions for this player name
        print("\n" + "="*80)
        print("Searching ALL Bluesky posts in database for 'Yesavage'...")
        print("="*80)

        all_bluesky = db.query(SocialMention).filter(
            SocialMention.platform == 'bluesky'
        ).all()

        print(f"\nTotal Bluesky posts in database: {len(all_bluesky)}")

        yesavage_posts = [m for m in all_bluesky if 'yesavage' in m.content.lower()]
        print(f"Posts mentioning 'Yesavage': {len(yesavage_posts)}")

        if yesavage_posts:
            print("\nThese Bluesky posts mention Yesavage:")
            for mention in yesavage_posts[:10]:
                linked_player = db.query(PlayerHype).filter(
                    PlayerHype.id == mention.player_hype_id
                ).first()
                print(f"\n  Linked to: {linked_player.player_name if linked_player else 'Unknown'}")
                print(f"  Content: {mention.content[:100]}...")
                print(f"  URL: {mention.url}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_trey()
