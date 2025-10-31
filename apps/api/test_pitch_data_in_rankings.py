"""
Test to verify pitch data IS being used in composite rankings
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os
sys.path.append('app')

# Ensure pitch metrics are ENABLED
os.environ['SKIP_PITCH_METRICS'] = 'false'

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test():
    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING COMPOSITE RANKINGS WITH PITCH METRICS ENABLED")
        print("SKIP_PITCH_METRICS =", os.getenv('SKIP_PITCH_METRICS', 'not set'))
        print("=" * 80)
        print()

        try:
            # Generate top 5 rankings
            print("Generating top 5 rankings...")
            rankings = await service.generate_prospect_rankings(limit=5)

            print(f"SUCCESS! Generated {len(rankings)} rankings\n")

            # Check each ranking for pitch data usage
            pitch_data_count = 0
            game_log_count = 0
            no_data_count = 0

            for i, prospect in enumerate(rankings, 1):
                details = prospect.get('performance_details', {})
                source = details.get('source', 'unknown')

                print(f"{i}. {prospect['name']:25s} - Score: {prospect.get('composite_score', 0):.1f}")

                if source == 'pitch_data':
                    pitch_data_count += 1
                    print(f"   DATA SOURCE: Pitch Data ({details.get('sample_size', 0)} pitches)")
                    print(f"   Composite Percentile: {details.get('composite_percentile', 0):.1f}th")
                elif source == 'game_logs':
                    game_log_count += 1
                    print(f"   DATA SOURCE: Game Logs (fallback)")
                else:
                    no_data_count += 1
                    print(f"   DATA SOURCE: None available")

                print()

            print("=" * 80)
            print(f"RESULTS:")
            print(f"  Pitch Data: {pitch_data_count}/{len(rankings)}")
            print(f"  Game Logs:  {game_log_count}/{len(rankings)}")
            print(f"  No Data:    {no_data_count}/{len(rankings)}")
            print("=" * 80)

            if pitch_data_count > 0:
                print("\nSUCCESS - Pitch data is being used!")
            else:
                print("\nWARNING - NO pitch data being used, only game logs")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
