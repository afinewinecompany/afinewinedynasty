"""
Test HYPE calculator for multiple players to verify fix
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.hype_calculator import HypeCalculator
from app.models.hype import PlayerHype

def test_multiple_players():
    """Test the HYPE calculator for multiple players"""
    db = SessionLocal()

    try:
        # Get top 5 players by ID
        players = db.query(PlayerHype).order_by(PlayerHype.id).limit(5).all()

        print(f"Testing HYPE calculator for {len(players)} players\n")
        print("="*70)

        calculator = HypeCalculator(db)
        success_count = 0
        fail_count = 0

        for player in players:
            print(f"\nTesting: {player.player_name} ({player.player_id})")
            print(f"  Current score: {player.hype_score}")

            try:
                result = calculator.calculate_hype_score(player.player_id)

                print(f"  [OK] SUCCESS")
                print(f"     New score: {result['hype_score']:.2f}")
                print(f"     24h mentions: {result['metrics']['social'].get('total_mentions_24h', 0)}")
                print(f"     Trend: {result['trend']:.2f}%")

                success_count += 1

            except Exception as e:
                print(f"  [FAIL] FAILED: {e}")
                fail_count += 1

        print("\n" + "="*70)
        print(f"SUMMARY:")
        print(f"  Total tested: {len(players)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {fail_count}")

        if fail_count == 0:
            print(f"\n[SUCCESS] ALL PLAYERS PASSED! HYPE calculator is working correctly.")
        else:
            print(f"\n[WARNING] {fail_count} players failed")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_multiple_players()
