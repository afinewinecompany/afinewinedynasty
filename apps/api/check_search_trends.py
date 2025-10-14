"""
Check if Google Trends data exists in the database
"""
from app.db.database import SyncSessionLocal
from app.models.hype import SearchTrend, PlayerHype
from sqlalchemy import func

db = SyncSessionLocal()

try:
    # Check total search trends records
    total_trends = db.query(func.count(SearchTrend.id)).scalar()
    print(f"Total SearchTrend records: {total_trends}")

    # Check total player hype records
    total_players = db.query(func.count(PlayerHype.id)).scalar()
    print(f"Total PlayerHype records: {total_players}")

    # Get a sample of players with hype data
    sample_players = db.query(PlayerHype).limit(5).all()
    print(f"\nSample players with hype data:")
    for player in sample_players:
        print(f"  - {player.player_name} (ID: {player.player_id}, Hype: {player.hype_score})")

    # Check if any players have search trends
    if total_trends > 0:
        sample_trends = db.query(SearchTrend).limit(3).all()
        print(f"\nSample SearchTrend records:")
        for trend in sample_trends:
            player = db.query(PlayerHype).filter(PlayerHype.id == trend.player_hype_id).first()
            print(f"  - Player: {player.player_name if player else 'Unknown'}")
            print(f"    Search Interest: {trend.search_interest}")
            print(f"    Growth Rate: {trend.search_growth_rate}%")
            print(f"    Collected: {trend.collected_at}")
    else:
        print("\n⚠️ No SearchTrend data found! Need to run collection.")

finally:
    db.close()
