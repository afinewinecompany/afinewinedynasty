"""
Check Hagen Smith's data to understand matching issues
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention, MediaArticle

def check_hagen():
    """Check Hagen Smith's data"""
    db = SessionLocal()

    try:
        # Find Hagen Smith
        player = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%hagen%smith%')
        ).first()

        if not player:
            print("ERROR: Hagen Smith not found in PlayerHype table")
            print("\nSearching for similar names:")
            players = db.query(PlayerHype).filter(
                PlayerHype.player_name.ilike('%smith%')
            ).limit(10).all()
            for p in players:
                print(f"  - {p.player_name} ({p.player_id})")
            return

        print(f"Found: {player.player_name}")
        print(f"Player ID: {player.player_id}")
        print(f"HYPE Score: {player.hype_score}")
        print(f"24h Mentions: {player.total_mentions_24h}")
        print(f"7d Mentions: {player.total_mentions_7d}")
        print()

        # Check social mentions
        mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id
        ).all()

        print(f"Social Mentions: {len(mentions)}")
        if mentions:
            print("\nRecent mentions:")
            for mention in mentions[:5]:
                print(f"  - Platform: {mention.platform}")
                print(f"    Content: {mention.content[:100]}...")
                print(f"    Posted: {mention.posted_at}")
                print()

        # Check media articles
        articles = db.query(MediaArticle).filter(
            MediaArticle.player_hype_id == player.id
        ).all()

        print(f"Media Articles: {len(articles)}")
        if articles:
            print("\nRecent articles:")
            for article in articles[:5]:
                print(f"  - Source: {article.source}")
                print(f"    Title: {article.title[:80]}...")
                print()

        # Now let's search Bluesky for Hagen Smith manually
        print("\n" + "="*80)
        print("Searching for potential Bluesky matches...")
        print("="*80)

        # Search all social mentions for "Hagen" or "Smith"
        all_mentions = db.query(SocialMention).filter(
            SocialMention.platform == 'bluesky'
        ).all()

        hagen_matches = []
        for mention in all_mentions:
            content_lower = mention.content.lower()
            if 'hagen' in content_lower and 'smith' in content_lower:
                hagen_matches.append(mention)

        print(f"\nFound {len(hagen_matches)} Bluesky posts mentioning 'Hagen Smith'")

        if hagen_matches:
            print("\nThese posts should be linked to Hagen Smith:")
            for i, mention in enumerate(hagen_matches[:10], 1):
                # Find which player it's currently linked to
                linked_player = db.query(PlayerHype).filter(
                    PlayerHype.id == mention.player_hype_id
                ).first()

                print(f"\n{i}. Currently linked to: {linked_player.player_name if linked_player else 'Unknown'}")
                print(f"   Content: {mention.content[:150]}...")
                print(f"   Posted: {mention.posted_at}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_hagen()
