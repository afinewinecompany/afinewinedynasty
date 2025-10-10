"""
Populate PlayerHype table with current prospects from prospects table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype
from app.db.models import Prospect
from datetime import datetime
import random

def populate_hype_from_prospects():
    """Populate PlayerHype table with data from prospects table"""
    db = SyncSessionLocal()

    try:
        # Get all prospects, preferring those with ETA year sooner
        prospects = db.query(Prospect).order_by(
            Prospect.eta_year.asc().nullslast()
        ).all()
        print(f"Found {len(prospects)} prospects in database")

        # Check existing PlayerHype entries
        existing_hype = db.query(PlayerHype).count()
        print(f"Existing PlayerHype entries: {existing_hype}")

        # Clear existing hype data for fresh start
        if existing_hype > 0:
            print("Clearing existing PlayerHype data...")
            db.query(PlayerHype).delete()
            db.commit()

        # Create PlayerHype entries for top prospects
        added_count = 0

        # Focus on top prospects (those with earliest ETA or random selection)
        top_prospects = prospects[:100] if len(prospects) > 100 else prospects

        for idx, prospect in enumerate(top_prospects):
            # Create a player_id from the name
            player_id = prospect.name.lower().replace(' ', '-').replace('.', '')

            # Generate realistic HYPE scores
            # Higher scores for prospects with sooner ETA years
            if prospect.eta_year:
                years_away = prospect.eta_year - 2025
                base_score = max(90 - (years_away * 10), 30)
            else:
                base_score = random.uniform(40, 70)

            hype_score = base_score + random.uniform(-10, 10)

            # Generate other metrics
            virality = random.uniform(40, 90) if idx < 20 else random.uniform(20, 60)
            sentiment = random.uniform(0.3, 0.9) if idx < 30 else random.uniform(-0.2, 0.7)
            trend = random.uniform(-10, 25) if idx < 20 else random.uniform(-15, 15)

            player_hype = PlayerHype(
                player_id=player_id,
                player_name=prospect.name,
                player_type='prospect',
                hype_score=round(min(100, max(0, hype_score)), 2),
                hype_trend=round(trend, 2),
                sentiment_score=round(sentiment, 3),
                virality_score=round(virality, 2),
                total_mentions_24h=int(random.uniform(100, 10000) * (100 - idx) / 100),
                total_mentions_7d=int(random.uniform(500, 50000) * (100 - idx) / 100),
                engagement_rate=round(random.uniform(2.0, 8.0), 2),
                last_calculated=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(player_hype)
            added_count += 1

            if added_count % 20 == 0:
                print(f"Added {added_count} PlayerHype entries...")

        db.commit()
        print(f"\nSuccessfully populated PlayerHype table with {added_count} prospects")

        # Display top 10 by HYPE score
        top_hype = db.query(PlayerHype).order_by(PlayerHype.hype_score.desc()).limit(10).all()
        print("\nTop 10 Players by HYPE Score:")
        for idx, player in enumerate(top_hype, 1):
            print(f"{idx}. {player.player_name}: {player.hype_score} (trend: {player.hype_trend:+.1f}%)")

    except Exception as e:
        print(f"Error populating hype data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_hype_from_prospects()