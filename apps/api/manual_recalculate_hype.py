"""Manually recalculate HYPE scores for specific players"""
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
    # Players to recalculate
    player_names = ['Michael Arroyo', 'Eli Willits']

    calculator = HypeCalculator(db)

    for player_name in player_names:
        print(f"\n{'='*80}")
        print(f"Recalculating HYPE for {player_name}")
        print('='*80)

        # Find player
        player = db.query(PlayerHype).filter(
            PlayerHype.player_name.ilike(f'%{player_name}%')
        ).first()

        if not player:
            print(f"✗ Player '{player_name}' not found")
            continue

        print(f"✓ Found: {player.player_name} ({player.player_id})")
        print(f"\nBEFORE:")
        print(f"  HYPE Score: {player.hype_score}")
        print(f"  Sentiment: {player.sentiment_score}")
        print(f"  Virality: {player.virality_score}")
        print(f"  Engagement Rate: {player.engagement_rate}%")
        print(f"  Mentions 24h: {player.total_mentions_24h}")

        # Calculate new scores
        result = calculator.calculate_hype_score(player.player_id)

        # Refresh from DB
        db.refresh(player)

        print(f"\nAFTER:")
        print(f"  HYPE Score: {player.hype_score} (Δ {player.hype_score - result['hype_score'] + result['hype_score']:.2f})")
        print(f"  Trend: {player.hype_trend:+.2f}%")
        print(f"  Sentiment: {player.sentiment_score:.3f}")
        print(f"  Virality: {player.virality_score:.2f}")
        print(f"  Engagement Rate: {player.engagement_rate:.2f}%")
        print(f"  Mentions 24h: {player.total_mentions_24h}")
        print(f"  Mentions 7d: {player.total_mentions_7d}")
        print(f"  Mentions 14d: {player.total_mentions_14d}")

        print(f"\n--- Score Components ---")
        print(f"  Social: {result['components']['social']:.2f}")
        print(f"  Media: {result['components']['media']:.2f}")
        print(f"  Virality: {result['components']['virality']:.2f}")
        print(f"  Sentiment: {result['components']['sentiment']:.2f}")

        print(f"\n--- Social Metrics ---")
        social = result['metrics']['social']
        print(f"  Total Engagement: {social['total_engagement']:.2f}")
        print(f"  Platform Breakdown: {social['platform_breakdown']}")

        print(f"\n✓ HYPE score updated successfully!")

    print(f"\n{'='*80}")
    print("All recalculations complete!")
    print('='*80)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
