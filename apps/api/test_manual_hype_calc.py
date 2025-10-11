"""
Manually test HYPE calculator with fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.hype_calculator import HypeCalculator
from app.models.hype import PlayerHype

def test_calculator():
    """Test the HYPE calculator for one player"""
    db = SessionLocal()

    try:
        # Get Colt Emerson
        player = db.query(PlayerHype).filter(
            PlayerHype.player_id == "colt-emerson"
        ).first()

        if not player:
            print("Player not found")
            return

        print(f"Testing HYPE calculator for: {player.player_name}")
        print(f"Current score: {player.hype_score}")
        print(f"Last calculated: {player.last_calculated}\n")

        calculator = HypeCalculator(db)

        print("Running calculator...")
        result = calculator.calculate_hype_score("colt-emerson")

        print(f"\nSUCCESS!")
        print(f"New HYPE Score: {result['hype_score']}")
        print(f"Trend: {result['trend']}%")
        print(f"Virality: {result['components']['virality']}")
        print(f"Sentiment: {result['components']['sentiment']}")
        print(f"24h Mentions: {result['metrics']['social'].get('total_mentions_24h', 0)}")
        print(f"7d Mentions: {result['metrics']['social'].get('total_mentions_7d', 0)}")

        # Verify the data was saved
        db.refresh(player)
        print(f"\nVerifying database:")
        print(f"DB HYPE Score: {player.hype_score}")
        print(f"DB 24h Mentions: {player.total_mentions_24h}")
        print(f"DB 7d Mentions: {player.total_mentions_7d}")
        print(f"DB Last Calculated: {player.last_calculated}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_calculator()
