"""Test HYPE calculation for Eli Willits"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from models.hype import PlayerHype
from services.hype_calculator import HypeCalculator

load_dotenv()

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('SQLALCHEMY_DATABASE_URI')
if 'asyncpg' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Find Eli Willits
    eli = db.query(PlayerHype).filter(
        PlayerHype.player_name.ilike('%eli willits%')
    ).first()

    if eli:
        print(f"Running HYPE calculator for {eli.player_name}...")
        print(f"Player ID: {eli.player_id}")
        print("=" * 80)

        # Run calculator
        calculator = HypeCalculator(db)
        result = calculator.calculate_hype_score(eli.player_id)

        print("\n" + "=" * 80)
        print("CALCULATION RESULTS:")
        print("=" * 80)

        print(f"\nFinal HYPE Score: {result['hype_score']:.2f}")
        print(f"Trend: {result['trend']:.2f}%")

        print("\n--- Components ---")
        for component, score in result['components'].items():
            print(f"  {component.capitalize()}: {score:.2f}")

        print("\n--- Social Metrics ---")
        social = result['metrics']['social']
        print(f"  Total Mentions (24h): {social['total_mentions_24h']}")
        print(f"  Total Mentions (7d): {social['total_mentions_7d']}")
        print(f"  Total Mentions (14d): {social['total_mentions_14d']}")
        print(f"  Total Engagement: {social['total_engagement']:.2f}")
        print(f"  Platform Breakdown: {social['platform_breakdown']}")

        print("\n--- Media Metrics ---")
        media = result['metrics']['media']
        print(f"  Total Articles: {media['total_articles']}")
        print(f"  Total Coverage: {media['total_coverage']:.2f}")
        print(f"  Source Breakdown: {media['source_breakdown']}")

        print("\n--- Virality Metrics ---")
        virality = result['metrics']['virality']
        print(f"  Mentions (1h): {virality['mentions_1h']}")
        print(f"  Mentions (6h): {virality['mentions_6h']}")
        print(f"  Mentions (24h): {virality['mentions_24h']}")
        print(f"  Growth Rate (6h): {virality['growth_rate_6h']:.2f}")
        print(f"  Growth Rate (24h): {virality['growth_rate_24h']:.2f}")
        print(f"  Unique Platforms: {virality['unique_platforms']}")

        print("\n--- Sentiment Metrics ---")
        sentiment = result['metrics']['sentiment']
        print(f"  Positive: {sentiment['positive']}")
        print(f"  Negative: {sentiment['negative']}")
        print(f"  Neutral: {sentiment['neutral']}")
        print(f"  Average: {sentiment['average']:.3f}")

        print("\n" + "=" * 80)
        print("Updated PlayerHype record in database")
        print("=" * 80)

    else:
        print("Eli Willits not found in database")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
