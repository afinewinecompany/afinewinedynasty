"""
Test Google Trends collection for a single player
"""
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype
from app.services.google_trends_collector import GoogleTrendsCollector

db = SyncSessionLocal()

try:
    # Get a player with decent hype score
    player = db.query(PlayerHype).filter(PlayerHype.hype_score > 20).first()

    if not player:
        print("No players with hype > 20 found")
        exit(1)

    print(f"Testing Google Trends collection for: {player.player_name}")
    print(f"Player ID: {player.player_id}")
    print(f"Player Hype ID: {player.id}")
    print(f"Current Hype Score: {player.hype_score}\n")

    # Initialize collector
    collector = GoogleTrendsCollector(db)

    # Collect trends for this player
    print("Collecting Google Trends data...")
    result = collector.collect_player_trends(
        player_name=player.player_name,
        player_hype_id=player.id,
        timeframe='today 7-d',  # Last 7 days
        geo='US'
    )

    print("\nCollection Results:")
    print(f"  Search Interest: {result['search_interest']}")
    print(f"  7-Day Average: {result['search_interest_avg_7d']}")
    print(f"  Growth Rate: {result['search_growth_rate']}%")
    print(f"  Regional Interest: {len(result['regional_interest'])} regions")
    print(f"  Related Queries: {len(result['related_queries'])}")
    print(f"  Rising Queries: {len(result['rising_queries'])}")

    if result['related_queries']:
        print(f"\n  Top Related Query: {result['related_queries'][0]['query']}")

    print("\n✓ Collection successful!")

except Exception as e:
    print(f"\n✗ Error collecting trends: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
