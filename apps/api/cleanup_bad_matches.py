"""
Clean up incorrectly matched media articles and social mentions
This removes articles/posts that don't actually mention the player's full name
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention, MediaArticle

def cleanup_bad_matches():
    """Remove articles and social mentions that don't actually mention the player"""
    db = SessionLocal()

    try:
        # Get all players
        players = db.query(PlayerHype).all()

        total_articles_removed = 0
        total_mentions_removed = 0

        print(f"Checking {len(players)} players for incorrectly matched content...")
        print("="*80)

        for player in players:
            player_name_lower = player.player_name.lower()
            articles_removed = 0
            mentions_removed = 0

            # Check media articles
            articles = db.query(MediaArticle).filter(
                MediaArticle.player_hype_id == player.id
            ).all()

            for article in articles:
                full_text = f"{article.title} {article.summary or ''}".lower()
                if player_name_lower not in full_text:
                    # Handle encoding issues with emojis/special chars
                    safe_title = article.title[:60].encode('ascii', 'ignore').decode('ascii')
                    print(f"  Removing article from {player.player_name}: {safe_title}...")
                    db.delete(article)
                    articles_removed += 1

            # Check social mentions
            mentions = db.query(SocialMention).filter(
                SocialMention.player_hype_id == player.id
            ).all()

            for mention in mentions:
                content_lower = mention.content.lower()
                if player_name_lower not in content_lower:
                    # Handle encoding issues with emojis/special chars
                    safe_content = mention.content[:60].encode('ascii', 'ignore').decode('ascii')
                    print(f"  Removing {mention.platform} mention from {player.player_name}: {safe_content}...")
                    db.delete(mention)
                    mentions_removed += 1

            if articles_removed > 0 or mentions_removed > 0:
                print(f"\n{player.player_name}:")
                print(f"  Removed {articles_removed} articles, {mentions_removed} social mentions")
                print()

            total_articles_removed += articles_removed
            total_mentions_removed += mentions_removed

        # Commit all deletions
        db.commit()

        print("="*80)
        print(f"SUMMARY:")
        print(f"  Total articles removed: {total_articles_removed}")
        print(f"  Total social mentions removed: {total_mentions_removed}")
        print(f"\nDatabase cleaned successfully!")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_bad_matches()
