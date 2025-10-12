"""
Check current status of HYPE scores in database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype

def check_status():
    """Check HYPE score status"""
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        # Get all players
        players = db.query(PlayerHype).all()

        print(f"HYPE Score Status Report")
        print(f"Generated: {now}")
        print("="*80)

        # Check how many have recent calculations
        recent_cutoff = now - timedelta(minutes=30)
        recent_count = sum(1 for p in players if p.last_calculated and p.last_calculated > recent_cutoff)

        print(f"\nTotal players: {len(players)}")
        print(f"Recently calculated (last 30 min): {recent_count}")
        print(f"Stale or never calculated: {len(players) - recent_count}")

        # Show top 10 by score
        print(f"\nTop 10 by HYPE Score:")
        print("-"*80)
        top_players = sorted(players, key=lambda p: p.hype_score if p.hype_score else 0, reverse=True)[:10]

        for i, player in enumerate(top_players, 1):
            age = "Never" if not player.last_calculated else f"{(now - player.last_calculated).total_seconds() / 60:.0f} min ago"
            print(f"{i:2}. {player.player_name:25} | Score: {player.hype_score:6.2f} | 24h: {player.total_mentions_24h:3} | Last: {age}")

        # Show players with mentions but low scores (potential calculation issues)
        print(f"\nPlayers with mentions but scores <= 10:")
        print("-"*80)
        low_score_with_mentions = [
            p for p in players
            if p.total_mentions_24h and p.total_mentions_24h > 0 and (p.hype_score or 0) <= 10
        ]

        if low_score_with_mentions:
            for player in low_score_with_mentions[:5]:
                age = "Never" if not player.last_calculated else f"{(now - player.last_calculated).total_seconds() / 60:.0f} min ago"
                print(f"  {player.player_name:25} | Score: {player.hype_score:6.2f} | 24h: {player.total_mentions_24h:3} | Last: {age}")
        else:
            print("  None found - all scores look appropriate!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_status()
