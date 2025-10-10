"""
Check if Tink Hence posts are in database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import SocialMention, PlayerHype

def check_posts():
    """Check for Tink Hence posts in database"""
    db = SessionLocal()

    try:
        # Find Tink Hence player
        player = db.query(PlayerHype).filter(
            PlayerHype.player_id == "tink-hence"
        ).first()

        if not player:
            print("Player 'tink-hence' not found in database")
            return

        print(f"Found player: {player.player_name} (ID: {player.player_id})")

        # Get Bluesky posts
        posts = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id,
            SocialMention.platform == 'bluesky'
        ).order_by(SocialMention.posted_at.desc()).all()

        print(f"\nFound {len(posts)} Bluesky posts")

        for i, post in enumerate(posts, 1):
            print(f"\n{i}. {post.author_handle}")
            print(f"   URL: {post.url}")
            print(f"   Posted: {post.posted_at}")
            print(f"   Content: {post.content[:80]}...")
            print(f"   Likes: {post.likes}, Comments: {post.comments}, Shares: {post.shares}")

    finally:
        db.close()

if __name__ == "__main__":
    check_posts()
