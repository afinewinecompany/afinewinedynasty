"""
Recalculate HYPE scores after cleaning bad matches
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.services.hype_calculator import HypeCalculator
from app.models.hype import PlayerHype

def recalculate_all():
    """Recalculate HYPE scores for all players"""
    db = SessionLocal()

    try:
        players = db.query(PlayerHype).all()

        print(f"Recalculating HYPE scores for {len(players)} players...")
        print("="*80)

        calculator = HypeCalculator(db)
        success = 0
        fail = 0

        for i, player in enumerate(players, 1):
            try:
                print(f"[{i}/{len(players)}] {player.player_name}...", end=" ")
                result = calculator.calculate_hype_score(player.player_id)
                print(f"Score: {result['hype_score']:.2f}, Mentions: {result['metrics']['social'].get('total_mentions_24h', 0)}")
                success += 1
            except Exception as e:
                print(f"FAILED: {e}")
                fail += 1

        print("="*80)
        print(f"SUCCESS: {success}/{len(players)}")
        if fail > 0:
            print(f"FAILED: {fail}/{len(players)}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    recalculate_all()
