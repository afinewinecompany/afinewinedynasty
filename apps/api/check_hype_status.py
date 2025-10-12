"""
Check current HYPE data status in the database
"""
import sys
import os
from dotenv import load_dotenv

# Load .env file FIRST
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention, MediaArticle
from sqlalchemy import func

def check_hype_status():
    """Check current status of HYPE data collection"""
    db = SessionLocal()

    try:
        print("HYPE DATA STATUS CHECK")
        print("="*80)
        print(f"Time: {datetime.now()}")
        print()

        # Total players
        total_players = db.query(PlayerHype).count()
        print(f"Total players in system: {total_players}")
        print()

        # Social mentions by platform
        print("SOCIAL MENTIONS BY PLATFORM:")
        platform_counts = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('total')
        ).group_by(SocialMention.platform).all()

        for platform, count in platform_counts:
            print(f"  {platform}: {count} mentions")

        total_mentions = db.query(SocialMention).count()
        print(f"  TOTAL: {total_mentions} mentions")
        print()

        # Recent mentions (last 24 hours)
        cutoff_24h = datetime.now() - timedelta(hours=24)
        recent_mentions = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('count')
        ).filter(
            SocialMention.created_at >= cutoff_24h
        ).group_by(SocialMention.platform).all()

        print("MENTIONS COLLECTED IN LAST 24 HOURS:")
        total_recent = 0
        for platform, count in recent_mentions:
            print(f"  {platform}: {count}")
            total_recent += count
        print(f"  TOTAL: {total_recent}")
        print()

        # Media articles
        total_articles = db.query(MediaArticle).count()
        recent_articles = db.query(MediaArticle).filter(
            MediaArticle.created_at >= cutoff_24h
        ).count()
        print(f"MEDIA ARTICLES:")
        print(f"  Total: {total_articles}")
        print(f"  Last 24h: {recent_articles}")
        print()

        # Check specific players
        print("SPECIFIC PLAYER CHECKS:")
        check_players = ['Trey Yesavage', 'Hagen Smith', 'Chase Burns', 'Travis Bazzana', 'Jac Caglianone']

        for player_name in check_players:
            player = db.query(PlayerHype).filter(
                PlayerHype.player_name.ilike(f'%{player_name}%')
            ).first()

            if player:
                # Get mention counts
                mentions = db.query(
                    SocialMention.platform,
                    func.count(SocialMention.id).label('count')
                ).filter(
                    SocialMention.player_hype_id == player.id
                ).group_by(SocialMention.platform).all()

                mentions_str = ", ".join([f"{p}={c}" for p, c in mentions]) if mentions else "none"

                print(f"  {player.player_name:20} - Score: {player.hype_score:6.2f}, "
                      f"14d: {player.total_mentions_14d:3}, Mentions: {mentions_str}")

        print()
        print("TOP 10 BY HYPE SCORE:")
        top_players = db.query(PlayerHype).order_by(
            PlayerHype.hype_score.desc()
        ).limit(10).all()

        for i, player in enumerate(top_players, 1):
            print(f"{i:2}. {player.player_name:25} | Score: {player.hype_score:6.2f} | "
                  f"24h: {player.total_mentions_24h:3} | "
                  f"7d: {player.total_mentions_7d:3} | "
                  f"14d: {player.total_mentions_14d:3}")

    finally:
        db.close()

if __name__ == "__main__":
    check_hype_status()