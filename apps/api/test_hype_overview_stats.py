"""
Test HYPE overview statistics for accuracy
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention, MediaArticle
from sqlalchemy import func
from datetime import datetime, timedelta

def check_player_stats(player_id: str):
    """Check stats for a specific player"""
    db = SessionLocal()

    try:
        # Get player
        player = db.query(PlayerHype).filter(
            PlayerHype.player_id == player_id
        ).first()

        if not player:
            print(f"Player '{player_id}' not found")
            return

        print(f"\n{'='*70}")
        print(f"HYPE Statistics for: {player.player_name}")
        print(f"{'='*70}\n")

        # Database values
        print("DATABASE VALUES (from PlayerHype table):")
        print(f"  HYPE Score: {player.hype_score}")
        print(f"  HYPE Trend: {player.hype_trend}%")
        print(f"  Virality Score: {player.virality_score}")
        print(f"  Sentiment Score: {player.sentiment_score}")
        print(f"  Total Mentions (24h): {player.total_mentions_24h}")
        print(f"  Total Mentions (7d): {player.total_mentions_7d}")
        print(f"  Engagement Rate: {player.engagement_rate}")
        print(f"  Last Calculated: {player.last_calculated}")

        # Count actual social mentions
        print(f"\nACTUAL DATA (from SocialMention table):")

        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        cutoff_7d = datetime.utcnow() - timedelta(days=7)

        mentions_24h = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id,
            SocialMention.posted_at >= cutoff_24h
        ).count()

        mentions_7d = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id,
            SocialMention.posted_at >= cutoff_7d
        ).count()

        total_mentions = db.query(SocialMention).filter(
            SocialMention.player_hype_id == player.id
        ).count()

        print(f"  Social Mentions (24h): {mentions_24h}")
        print(f"  Social Mentions (7d): {mentions_7d}")
        print(f"  Total Social Mentions: {total_mentions}")

        # Breakdown by platform
        by_platform = db.query(
            SocialMention.platform,
            func.count(SocialMention.id).label('count')
        ).filter(
            SocialMention.player_hype_id == player.id
        ).group_by(SocialMention.platform).all()

        if by_platform:
            print(f"\n  By Platform:")
            for platform, count in by_platform:
                print(f"    - {platform}: {count} posts")

        # Media articles
        media_count = db.query(MediaArticle).filter(
            MediaArticle.player_hype_id == player.id
        ).count()

        print(f"\n  Media Articles: {media_count}")

        # Calculate average engagement
        if total_mentions > 0:
            avg_engagement = db.query(
                func.avg(SocialMention.likes + SocialMention.shares + SocialMention.comments)
            ).filter(
                SocialMention.player_hype_id == player.id
            ).scalar()

            print(f"\n  Average Engagement per Post: {avg_engagement:.1f}" if avg_engagement else "\n  Average Engagement: N/A")

        # Sentiment distribution
        sentiment_dist = db.query(
            SocialMention.sentiment,
            func.count(SocialMention.id).label('count')
        ).filter(
            SocialMention.player_hype_id == player.id
        ).group_by(SocialMention.sentiment).all()

        if sentiment_dist:
            print(f"\n  Sentiment Distribution:")
            for sentiment, count in sentiment_dist:
                print(f"    - {sentiment}: {count} ({count/total_mentions*100:.1f}%)")

        # VALIDATION
        print(f"\n{'='*70}")
        print("VALIDATION:")
        print(f"{'='*70}")

        issues = []

        if player.total_mentions_24h != mentions_24h:
            issues.append(f"24h mentions mismatch: DB says {player.total_mentions_24h}, actual is {mentions_24h}")

        if player.total_mentions_7d != mentions_7d:
            issues.append(f"7d mentions mismatch: DB says {player.total_mentions_7d}, actual is {mentions_7d}")

        if not player.last_calculated:
            issues.append("HYPE score never calculated (last_calculated is None)")
        elif (datetime.utcnow() - player.last_calculated).total_seconds() > 3600:
            issues.append(f"HYPE score stale (calculated {(datetime.utcnow() - player.last_calculated).total_seconds() / 60:.0f} minutes ago)")

        if issues:
            print("\n  ISSUES FOUND:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("\n  All statistics appear accurate!")

    finally:
        db.close()

if __name__ == "__main__":
    # Test with a few players
    test_players = ["colt-emerson", "tink-hence", "thomas-white"]

    for player_id in test_players:
        check_player_stats(player_id)
        print("\n")
