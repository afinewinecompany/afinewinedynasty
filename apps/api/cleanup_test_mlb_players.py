"""
Cleanup script to remove test MLB players from PlayerHype table
These were created during Google Trends testing
"""
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend

db = SyncSessionLocal()

try:
    print("Cleaning up test MLB players from PlayerHype table...\n")

    # Find all MLB players
    mlb_players = db.query(PlayerHype).filter(
        PlayerHype.player_type == 'mlb'
    ).all()

    print(f"Found {len(mlb_players)} MLB players:")
    for player in mlb_players:
        print(f"  - {player.player_name} (ID: {player.player_id}, Hype: {player.hype_score})")

    if not mlb_players:
        print("\nNo MLB players to clean up. Database is clean!")
        exit(0)

    print(f"\nRemoving {len(mlb_players)} MLB players...")

    for player in mlb_players:
        # Delete associated search trends first
        trends_deleted = db.query(SearchTrend).filter(
            SearchTrend.player_hype_id == player.id
        ).delete()

        print(f"  - Removing {player.player_name} ({trends_deleted} search trends)")

        # Delete the player
        db.delete(player)

    db.commit()

    print(f"\n✓ Cleanup complete!")
    print(f"  - Removed {len(mlb_players)} MLB players")
    print(f"  - Removed associated search trends")

    # Verify
    remaining_mlb = db.query(PlayerHype).filter(
        PlayerHype.player_type == 'mlb'
    ).count()

    remaining_prospects = db.query(PlayerHype).filter(
        PlayerHype.player_type == 'prospect'
    ).count()

    print(f"\nFinal count:")
    print(f"  - MLB players: {remaining_mlb}")
    print(f"  - Prospects: {remaining_prospects}")

finally:
    db.close()
