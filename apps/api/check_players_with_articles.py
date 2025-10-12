"""
Check which players have media articles
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, MediaArticle
from sqlalchemy import func

def check():
    """Check players with articles"""
    db = SessionLocal()

    try:
        # Get players with article counts
        results = db.query(
            PlayerHype.player_id,
            PlayerHype.player_name,
            func.count(MediaArticle.id).label('article_count')
        ).join(MediaArticle).group_by(
            PlayerHype.id,
            PlayerHype.player_id,
            PlayerHype.player_name
        ).all()

        print(f"Found {len(results)} players with media articles:\n")
        for player_id, player_name, count in results:
            print(f"{player_name} ({player_id}): {count} articles")

            # Show first article for this player
            article = db.query(MediaArticle).join(PlayerHype).filter(
                PlayerHype.player_id == player_id
            ).first()

            if article:
                print(f"  Sample: {article.title[:60]}...")
                print(f"  URL: {article.url}")
                print()

    finally:
        db.close()

if __name__ == "__main__":
    check()
