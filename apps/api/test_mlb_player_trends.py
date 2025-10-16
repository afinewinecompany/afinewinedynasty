"""
Test Google Trends with a popular MLB player
"""
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend
from app.services.google_trends_collector import GoogleTrendsCollector

db = SyncSessionLocal()

try:
    # Try with a well-known MLB player (create temporary hype record)
    test_players = ["Shohei Ohtani", "Aaron Judge", "Paul Skenes"]

    for player_name in test_players:
        print(f"\n{'='*60}")
        print(f"Testing with: {player_name}")
        print('='*60)

        # Check if player already has hype data
        player = db.query(PlayerHype).filter(PlayerHype.player_name == player_name).first()

        if not player:
            # Create temporary hype record
            player = PlayerHype(
                player_id=player_name.lower().replace(' ', '-'),
                player_name=player_name,
                player_type='mlb',
                hype_score=50.0
            )
            db.add(player)
            db.commit()
            print(f"Created temporary hype record for {player_name}")

        # Initialize collector
        collector = GoogleTrendsCollector(db)

        # Collect trends
        print("Collecting Google Trends data...")
        result = collector.collect_player_trends(
            player_name=player.player_name,
            player_hype_id=player.id,
            timeframe='today 1-m',  # Last month for better data
            geo='US'
        )

        print(f"\nResults for {player_name}:")
        print(f"  Search Interest: {result['search_interest']}")
        print(f"  7-Day Average: {result['search_interest_avg_7d']}")
        print(f"  Growth Rate: {result['search_growth_rate']}%")
        print(f"  Regional Interest: {len(result['regional_interest'])} regions")
        print(f"  Related Queries: {len(result['related_queries'])}")
        print(f"  Rising Queries: {len(result['rising_queries'])}")

        if result['related_queries']:
            print(f"\n  Top 3 Related Queries:")
            for q in result['related_queries'][:3]:
                print(f"    - {q['query']} (interest: {q['value']})")

        if result['regional_interest']:
            print(f"\n  Top 3 Regions:")
            for region, interest in list(result['regional_interest'].items())[:3]:
                print(f"    - {region}: {interest}")

        # If we got data, break
        if result['search_interest'] > 0:
            print(f"\nSUCCESS! Got trends data for {player_name}")
            break

    # Check what's in database now
    total_trends = db.query(SearchTrend).count()
    print(f"\n\nTotal SearchTrend records in database: {total_trends}")

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
