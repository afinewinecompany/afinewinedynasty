"""
Test social collection for multiple players
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype, SocialMention
from app.services.social_collector import SocialMediaCollector

async def test_multiple_players():
    """Test collecting for multiple players"""
    db = SessionLocal()

    try:
        # Get first 5 PlayerHype records
        players = db.query(PlayerHype).limit(5).all()

        print(f"Testing collection for {len(players)} players:")
        for p in players:
            print(f"  - {p.player_name} (ID: {p.player_id})")

        collector = SocialMediaCollector(db)

        for player in players:
            print(f"\n{'='*60}")
            print(f"Collecting data for {player.player_name}...")
            print(f"{'='*60}")

            try:
                # Collect Bluesky data
                result = await collector.collect_bluesky_data(
                    player.player_name,
                    player.player_id
                )

                print(f"\nBluesky: {result['status']}")
                if result['status'] == 'success':
                    print(f"  Collected {result['count']} posts")

                # Check what's in database for this player
                mentions = db.query(SocialMention).filter(
                    SocialMention.player_hype_id == player.id,
                    SocialMention.platform == 'bluesky'
                ).count()
                print(f"  Total Bluesky posts in DB: {mentions}")

            except Exception as e:
                print(f"Error: {e}")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        for player in players:
            total = db.query(SocialMention).filter(
                SocialMention.player_hype_id == player.id
            ).count()
            print(f"{player.player_name}: {total} total social mentions")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_multiple_players())
