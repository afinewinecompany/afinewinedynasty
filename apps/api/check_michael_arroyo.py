"""Check Michael Arroyo HYPE data"""
import os
import sys
import io

# Set UTF-8 encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from models.hype import PlayerHype, SocialMention, MediaArticle
from dotenv import load_dotenv

load_dotenv()

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL or SQLALCHEMY_DATABASE_URI not found in environment")
    sys.exit(1)

# Convert asyncpg to psycopg2 if needed
if 'asyncpg' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Find Michael Arroyo in PlayerHype
    print("=" * 80)
    print("Checking Michael Arroyo HYPE Data")
    print("=" * 80)

    michael = db.query(PlayerHype).filter(
        PlayerHype.player_name.ilike('%michael arroyo%')
    ).first()

    if michael:
        print(f"\n✓ Found PlayerHype record:")
        print(f"  ID: {michael.id}")
        print(f"  Player ID: {michael.player_id}")
        print(f"  Player Name: {michael.player_name}")
        print(f"  Player Type: {michael.player_type}")
        print(f"  HYPE Score: {michael.hype_score}")
        print(f"  HYPE Trend: {michael.hype_trend}")
        print(f"  Sentiment Score: {michael.sentiment_score}")
        print(f"  Virality Score: {michael.virality_score}")
        print(f"  Total Mentions 24h: {michael.total_mentions_24h}")
        print(f"  Total Mentions 7d: {michael.total_mentions_7d}")
        print(f"  Total Mentions 14d: {michael.total_mentions_14d}")
        print(f"  Engagement Rate: {michael.engagement_rate}")
        print(f"  Last Calculated: {michael.last_calculated}")

        # Check social mentions
        print(f"\n" + "=" * 80)
        print("Social Mentions with HIGH ENGAGEMENT:")
        print("=" * 80)

        social_count = db.query(func.count(SocialMention.id)).filter(
            SocialMention.player_hype_id == michael.id
        ).scalar()
        print(f"\nTotal Social Mentions: {social_count}")

        if social_count > 0:
            # Get mentions with engagement
            mentions_with_engagement = db.query(SocialMention).filter(
                SocialMention.player_hype_id == michael.id,
                (SocialMention.likes > 0) | (SocialMention.shares > 0) | (SocialMention.comments > 0)
            ).order_by(SocialMention.posted_at.desc()).limit(10).all()

            print(f"\nMentions with engagement (top 10):")
            total_engagement = 0
            for m in mentions_with_engagement:
                engagement = m.likes + m.shares + m.comments
                total_engagement += engagement
                print(f"\n  Posted: {m.posted_at}")
                print(f"  Platform: {m.platform}")
                print(f"  Author: {m.author_handle} (followers: {m.author_followers})")
                print(f"  Likes: {m.likes}, Shares: {m.shares}, Comments: {m.comments}")
                print(f"  Total Engagement: {engagement}")
                print(f"  Sentiment: {m.sentiment}")
                print(f"  Content: {m.content[:100]}...")

            print(f"\n  TOTAL RAW ENGAGEMENT (top 10): {total_engagement}")

            # Get ALL mentions
            all_mentions = db.query(SocialMention).filter(
                SocialMention.player_hype_id == michael.id
            ).all()

            total_all_engagement = sum(m.likes + m.shares + m.comments for m in all_mentions)
            avg_engagement = total_all_engagement / len(all_mentions) if all_mentions else 0

            print(f"\n  TOTAL ENGAGEMENT (all {len(all_mentions)} mentions): {total_all_engagement}")
            print(f"  AVERAGE ENGAGEMENT per mention: {avg_engagement:.2f}")

            # Time window analysis
            now = datetime.utcnow()

            # Check different time windows
            for window_name, window_hours in [('1 hour', 1), ('6 hours', 6), ('24 hours', 24), ('3 days', 72), ('7 days', 168), ('14 days', 336)]:
                window_time = now - timedelta(hours=window_hours)
                count = db.query(func.count(SocialMention.id)).filter(
                    SocialMention.player_hype_id == michael.id,
                    SocialMention.posted_at >= window_time
                ).scalar()

                total_eng = db.query(
                    func.sum(SocialMention.likes + SocialMention.shares + SocialMention.comments)
                ).filter(
                    SocialMention.player_hype_id == michael.id,
                    SocialMention.posted_at >= window_time
                ).scalar() or 0

                print(f"\n  Last {window_name}: {count} mentions, {total_eng} total engagement")

        # Check media articles
        print(f"\n" + "=" * 80)
        print("Media Articles:")
        print("=" * 80)

        media_count = db.query(func.count(MediaArticle.id)).filter(
            MediaArticle.player_hype_id == michael.id
        ).scalar()
        print(f"\nTotal Media Articles: {media_count}")

        if media_count > 0:
            recent_articles = db.query(MediaArticle).filter(
                MediaArticle.player_hype_id == michael.id
            ).order_by(MediaArticle.published_at.desc()).limit(5).all()

            print(f"\nRecent articles (last 5):")
            for a in recent_articles:
                print(f"\n  Source: {a.source}")
                print(f"  Published: {a.published_at}")
                print(f"  Title: {a.title}")
                print(f"  Sentiment: {a.sentiment}")
                print(f"  Prominence: {a.prominence_score}")

        print(f"\n" + "=" * 80)
        print("Analysis:")
        print("=" * 80)

        if social_count > 0:
            if total_all_engagement > 0:
                print(f"\n✓ Michael Arroyo has {total_all_engagement} total engagement across {social_count} mentions")
                print(f"  Average {avg_engagement:.2f} engagement per mention")

                if michael.hype_score == 0 or michael.engagement_rate == 0:
                    print("\n⚠ WARNING: Has engagement data but HYPE score or engagement rate is ZERO!")
                    print("  This suggests the HYPE calculator needs to be re-run.")
                else:
                    print(f"\n✓ HYPE Score is {michael.hype_score} (calculated)")
            else:
                print("\n⚠ Has mentions but ZERO engagement (no likes, shares, comments)")
        else:
            print("\n✗ No social mentions found")

    else:
        print("\n✗ No PlayerHype record found for Michael Arroyo")

        # Search for similar names
        print("\nSearching for similar player names...")
        similar = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%arroyo%')
        ).all()

        if similar:
            print(f"\nFound {len(similar)} similar players:")
            for p in similar:
                print(f"  - {p.player_name} ({p.player_id})")
        else:
            print("  No similar names found")

finally:
    db.close()
    print("\n" + "=" * 80)
