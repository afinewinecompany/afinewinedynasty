"""Check Eli Willits HYPE data"""
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
    # Find Eli Willits in PlayerHype
    print("=" * 80)
    print("Checking Eli Willits HYPE Data")
    print("=" * 80)

    eli = db.query(PlayerHype).filter(
        PlayerHype.player_name.ilike('%eli willits%')
    ).first()

    if eli:
        print(f"\n✓ Found PlayerHype record:")
        print(f"  ID: {eli.id}")
        print(f"  Player ID: {eli.player_id}")
        print(f"  Player Name: {eli.player_name}")
        print(f"  Player Type: {eli.player_type}")
        print(f"  HYPE Score: {eli.hype_score}")
        print(f"  HYPE Trend: {eli.hype_trend}")
        print(f"  Sentiment Score: {eli.sentiment_score}")
        print(f"  Virality Score: {eli.virality_score}")
        print(f"  Total Mentions 24h: {eli.total_mentions_24h}")
        print(f"  Total Mentions 7d: {eli.total_mentions_7d}")
        print(f"  Total Mentions 14d: {eli.total_mentions_14d}")
        print(f"  Engagement Rate: {eli.engagement_rate}")
        print(f"  Last Calculated: {eli.last_calculated}")

        # Check social mentions
        print(f"\n" + "=" * 80)
        print("Social Mentions:")
        print("=" * 80)

        social_count = db.query(func.count(SocialMention.id)).filter(
            SocialMention.player_hype_id == eli.id
        ).scalar()
        print(f"\nTotal Social Mentions: {social_count}")

        if social_count > 0:
            # Get recent mentions
            recent_mentions = db.query(SocialMention).filter(
                SocialMention.player_hype_id == eli.id
            ).order_by(SocialMention.posted_at.desc()).limit(5).all()

            print(f"\nRecent mentions (last 5):")
            for m in recent_mentions:
                print(f"\n  Platform: {m.platform}")
                print(f"  Posted: {m.posted_at}")
                print(f"  Author: {m.author_handle} (followers: {m.author_followers})")
                print(f"  Likes: {m.likes}, Shares: {m.shares}, Comments: {m.comments}")
                print(f"  Sentiment: {m.sentiment}")
                print(f"  Content: {m.content[:100]}...")

            # Time window analysis
            now = datetime.utcnow()
            mentions_24h = db.query(func.count(SocialMention.id)).filter(
                SocialMention.player_hype_id == eli.id,
                SocialMention.posted_at >= now - timedelta(hours=24)
            ).scalar()

            mentions_7d = db.query(func.count(SocialMention.id)).filter(
                SocialMention.player_hype_id == eli.id,
                SocialMention.posted_at >= now - timedelta(days=7)
            ).scalar()

            mentions_14d = db.query(func.count(SocialMention.id)).filter(
                SocialMention.player_hype_id == eli.id,
                SocialMention.posted_at >= now - timedelta(days=14)
            ).scalar()

            print(f"\nTime Window Breakdown:")
            print(f"  Last 24 hours: {mentions_24h}")
            print(f"  Last 7 days: {mentions_7d}")
            print(f"  Last 14 days: {mentions_14d}")

        # Check media articles
        print(f"\n" + "=" * 80)
        print("Media Articles:")
        print("=" * 80)

        media_count = db.query(func.count(MediaArticle.id)).filter(
            MediaArticle.player_hype_id == eli.id
        ).scalar()
        print(f"\nTotal Media Articles: {media_count}")

        if media_count > 0:
            recent_articles = db.query(MediaArticle).filter(
                MediaArticle.player_hype_id == eli.id
            ).order_by(MediaArticle.published_at.desc()).limit(5).all()

            print(f"\nRecent articles (last 5):")
            for a in recent_articles:
                print(f"\n  Source: {a.source}")
                print(f"  Published: {a.published_at}")
                print(f"  Title: {a.title}")
                print(f"  Sentiment: {a.sentiment}")
                print(f"  Prominence: {a.prominence_score}")
                print(f"  Summary: {a.summary[:100]}...")

            # Time window analysis
            articles_24h = db.query(func.count(MediaArticle.id)).filter(
                MediaArticle.player_hype_id == eli.id,
                MediaArticle.published_at >= now - timedelta(hours=24)
            ).scalar()

            articles_7d = db.query(func.count(MediaArticle.id)).filter(
                MediaArticle.player_hype_id == eli.id,
                MediaArticle.published_at >= now - timedelta(days=7)
            ).scalar()

            articles_14d = db.query(func.count(MediaArticle.id)).filter(
                MediaArticle.player_hype_id == eli.id,
                MediaArticle.published_at >= now - timedelta(days=14)
            ).scalar()

            print(f"\nTime Window Breakdown:")
            print(f"  Last 24 hours: {articles_24h}")
            print(f"  Last 7 days: {articles_7d}")
            print(f"  Last 14 days: {articles_14d}")

        print(f"\n" + "=" * 80)
        print("Analysis:")
        print("=" * 80)

        if social_count == 0 and media_count == 0:
            print("\n⚠ NO data found in social mentions or media articles!")
            print("  This explains why all metrics show zero.")
        elif eli.hype_score == 0 and (social_count > 0 or media_count > 0):
            print("\n⚠ WARNING: Data exists but HYPE score is zero!")
            print("  This suggests the HYPE calculator has not been run.")
            print("  Or the data is too old to contribute to the score.")
        else:
            print("\n✓ Data looks normal")

    else:
        print("\n✗ No PlayerHype record found for Eli Willits")

        # Search for similar names
        print("\nSearching for similar player names...")
        similar = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike('%willits%')
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
