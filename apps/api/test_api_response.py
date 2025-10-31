"""
Test actual API response to verify performance_breakdown is present
"""
import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test():
    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING API RESPONSE STRUCTURE")
        print("=" * 80)
        print()

        # Generate 3 rankings
        rankings = await service.generate_prospect_rankings(limit=3)

        print(f"Generated {len(rankings)} rankings\n")

        for i, prospect in enumerate(rankings, 1):
            print(f"\n{'='*80}")
            print(f"PROSPECT #{i}: {prospect['name']}")
            print(f"{'='*80}")

            # Check scores structure
            scores = prospect.get('scores', {})
            print(f"\nScores keys: {list(scores.keys())}")

            # Check for performance_breakdown
            if 'performance_breakdown' in scores:
                breakdown = scores['performance_breakdown']
                print(f"\nperformance_breakdown EXISTS!")
                print(f"  Keys: {list(breakdown.keys())}")
                print(f"  Source: {breakdown.get('source')}")

                if breakdown.get('source') == 'pitch_data':
                    print(f"  Sample Size: {breakdown.get('sample_size')}")
                    print(f"  Composite Percentile: {breakdown.get('composite_percentile')}")

                    metrics = breakdown.get('metrics', {})
                    print(f"\n  Metrics available:")
                    for key, value in metrics.items():
                        if value is not None:
                            print(f"    - {key}: {value}")
                else:
                    print(f"  Using game logs fallback")
            else:
                print(f"\nperformance_breakdown MISSING!")

            # Show the full scores dict structure
            print(f"\n  Full scores dict:")
            print(f"    composite_score: {scores.get('composite_score')}")
            print(f"    base_fv: {scores.get('base_fv')}")
            print(f"    performance_modifier: {scores.get('performance_modifier')}")
            print(f"    trend_adjustment: {scores.get('trend_adjustment')}")
            print(f"    age_adjustment: {scores.get('age_adjustment')}")

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test())
