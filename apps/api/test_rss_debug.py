"""
Debug RSS collection - check player matching
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SyncSessionLocal as SessionLocal
from app.models.hype import PlayerHype
from app.db.models import Prospect

def debug_player_matching():
    """Debug player matching logic"""
    db = SessionLocal()

    try:
        # Get all prospects and player hypes
        prospects = db.query(Prospect).limit(10).all()
        player_hypes = db.query(PlayerHype).limit(10).all()

        print("=== PROSPECTS ===")
        print(f"Total: {db.query(Prospect).count()}")
        print("\nFirst 10:")
        for p in prospects:
            print(f"  {p.name} -> prospect_{p.mlb_id}")

        print("\n=== PLAYER HYPE ===")
        print(f"Total: {db.query(PlayerHype).count()}")
        print("\nFirst 10:")
        for p in player_hypes:
            print(f"  {p.player_name} -> {p.player_id}")

        # Test sample article text
        print("\n=== TEST ARTICLE ===")
        test_text = "Colt Emerson and JJ Wetherholt are top prospects for 2025"
        print(f"Article: {test_text}")

        # Build player name lookup like RSS collector does
        player_names = {}

        for prospect in prospects:
            name = prospect.name
            player_names[name.lower()] = f"prospect_{prospect.mlb_id}"
            last_name = name.split()[-1] if ' ' in name else name
            if len(last_name) > 4:
                player_names[last_name.lower()] = f"prospect_{prospect.mlb_id}"

        for player_hype in player_hypes:
            name = player_hype.player_name
            player_names[name.lower()] = player_hype.player_id
            last_name = name.split()[-1] if ' ' in name else name
            if len(last_name) > 4:
                player_names[last_name.lower()] = player_hype.player_id

        print(f"\nPlayer name lookup has {len(player_names)} entries")
        print("\nFirst 10 entries:")
        for i, (name, pid) in enumerate(list(player_names.items())[:10]):
            print(f"  '{name}' -> {pid}")

        # Find matches
        print("\nMatches in test article:")
        full_text = test_text.lower()
        for player_name, player_id in player_names.items():
            if player_name in full_text:
                print(f"  Found '{player_name}' -> {player_id}")

                # Try to find PlayerHype
                player_hype = db.query(PlayerHype).filter(
                    PlayerHype.player_id == player_id
                ).first()

                if player_hype:
                    print(f"    ✓ Found PlayerHype record")
                else:
                    print(f"    ✗ NO PlayerHype record found for ID: {player_id}")

    finally:
        db.close()

if __name__ == "__main__":
    debug_player_matching()
