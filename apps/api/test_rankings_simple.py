"""
Simple test of composite rankings with pitch metrics enabled
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_rankings():
    """Test that rankings work with pitch metrics enabled"""

    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING COMPOSITE RANKINGS WITH PITCH METRICS ENABLED")
        print("=" * 80)
        print()

        try:
            # Generate top 10 rankings
            print("Generating top 10 rankings...")
            rankings = await service.generate_prospect_rankings(limit=10)

            print(f"SUCCESS! Generated {len(rankings)} rankings\n")

            # Show results
            print("Top 10 Prospects:")
            print("-" * 80)
            for i, prospect in enumerate(rankings, 1):
                print(f"{i:2d}. {prospect['name']:25s} {prospect['composite_score']:5.1f}")
                print(f"     Base FV: {prospect.get('base_fv', 0):.1f}, "
                      f"Perf Mod: {prospect.get('performance_modifier', 0):+.1f}, "
                      f"Trend: {prospect.get('trend_adjustment', 0):+.1f}")

                # Check if pitch metrics were used
                if 'performance_details' in prospect and prospect['performance_details']:
                    details = prospect['performance_details']
                    if details.get('source') == 'pitch_data':
                        print(f"     DATA SOURCE: Pitch Data ({details.get('sample_size', 0)} pitches)")
                    elif details.get('source') == 'game_logs':
                        print(f"     DATA SOURCE: Game Logs")
                    else:
                        print(f"     DATA SOURCE: None available")

                print()

            # Count pitch data usage
            pitch_data_count = sum(
                1 for p in rankings
                if p.get('performance_details', {}).get('source') == 'pitch_data'
            )

            print("=" * 80)
            print(f"SUMMARY: {pitch_data_count}/{len(rankings)} prospects using pitch-level data")
            print("=" * 80)

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rankings())
