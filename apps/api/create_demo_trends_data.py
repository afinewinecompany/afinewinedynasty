"""
Create demo Google Trends data for testing the frontend
"""
from datetime import datetime, timedelta
from app.db.database import SyncSessionLocal
from app.models.hype import PlayerHype, SearchTrend
import random

db = SyncSessionLocal()

try:
    # Get top 10 players by hype score
    top_players = db.query(PlayerHype).order_by(PlayerHype.hype_score.desc()).limit(10).all()

    print(f"Creating demo Google Trends data for {len(top_players)} players...\n")

    for idx, player in enumerate(top_players):
        # Generate realistic demo data
        base_interest = random.uniform(20, 80)
        growth_rate = random.uniform(-30, 50)

        # Generate regional data
        states = ['California', 'New York', 'Texas', 'Florida', 'Illinois',
                  'Pennsylvania', 'Ohio', 'Georgia', 'North Carolina', 'Michigan']
        regional_interest = {
            state: int(random.uniform(40, 100))
            for state in random.sample(states, k=random.randint(5, 8))
        }

        # Generate related queries
        related_queries = [
            {'query': f'{player.player_name} stats', 'value': random.randint(50, 100)},
            {'query': f'{player.player_name} highlights', 'value': random.randint(40, 90)},
            {'query': f'{player.player_name} news', 'value': random.randint(30, 80)},
            {'query': f'{player.player_name} trade', 'value': random.randint(20, 70)},
        ]

        # Generate rising queries (some breakout, some with percentages)
        rising_queries = [
            {'query': f'{player.player_name} contract', 'value': 'Breakout'},
            {'query': f'{player.player_name} injury', 'value': f'+{random.randint(100, 500)}%'},
            {'query': f'{player.player_name} team', 'value': f'+{random.randint(50, 200)}%'},
        ]

        # Create SearchTrend record
        search_trend = SearchTrend(
            player_hype_id=player.id,
            search_interest=base_interest,
            search_interest_avg_7d=base_interest * 0.9,
            search_interest_avg_30d=base_interest * 0.85,
            search_growth_rate=growth_rate,
            region='US',
            regional_interest=regional_interest,
            related_queries=related_queries,
            rising_queries=rising_queries,
            collected_at=datetime.utcnow(),
            data_period_start=datetime.utcnow() - timedelta(days=30),
            data_period_end=datetime.utcnow()
        )

        db.add(search_trend)

        print(f"{idx+1}. {player.player_name}")
        print(f"   Search Interest: {base_interest:.1f}")
        print(f"   Growth Rate: {growth_rate:+.1f}%")
        print(f"   Regions: {len(regional_interest)}")
        print(f"   Related Queries: {len(related_queries)}")
        print()

    db.commit()

    total_trends = db.query(SearchTrend).count()
    print(f"\n✓ Created demo trends data!")
    print(f"Total SearchTrend records: {total_trends}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()

finally:
    db.close()
