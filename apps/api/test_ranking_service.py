"""Test script for the prospect ranking service."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.prospect_ranking_service import ProspectRankingService
import os

# Database URL
DATABASE_URL = "postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def test_ranking_service():
    """Test the prospect ranking service."""
    print("\n" + "="*80)
    print("TESTING PROSPECT RANKING SERVICE")
    print("="*80 + "\n")

    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Initialize service
        service = ProspectRankingService(session)

        print("[OK] Initialized ProspectRankingService\n")

        # Test 1: Generate top 10 rankings
        print("[TEST 1] Generate Top 10 Overall Rankings")
        print("-" * 80)

        try:
            rankings = await service.generate_prospect_rankings(limit=10)

            print(f"[OK] Successfully generated {len(rankings)} rankings\n")

            # Display results
            print(f"{'Rank':<6} {'Name':<25} {'Pos':<5} {'FV':<6} {'Comp':<6} {'Adj':<6} {'Trend':<12}")
            print("-" * 80)

            for prospect in rankings:
                rank = prospect['rank']
                name = prospect['name'][:24]
                position = prospect['position']
                fv = prospect['scores']['base_fv']
                composite = prospect['scores']['composite_score']
                adjustment = prospect['scores']['total_adjustment']
                trend = await service.get_trend_indicator(prospect['scores']['trend_adjustment'])

                print(f"#{rank:<5} {name:<25} {position:<5} {fv:<6.1f} {composite:<6.1f} {adjustment:+5.1f}  {trend:<12}")

            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")
            import traceback
            traceback.print_exc()

        # Test 2: Filter by position (SS)
        print("\n[TEST 2] Top 5 Shortstops")
        print("-" * 80)

        try:
            ss_rankings = await service.generate_prospect_rankings(
                position_filter='SS',
                limit=5
            )

            print(f"[OK] Found {len(ss_rankings)} shortstops\n")

            for prospect in ss_rankings:
                print(f"#{prospect['rank']} {prospect['name']} - FV: {prospect['scores']['base_fv']}, Composite: {prospect['scores']['composite_score']}")

            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")

        # Test 3: Test score calculation components
        print("\n[TEST 3] Score Breakdown (Top Prospect)")
        print("-" * 80)

        try:
            rankings = await service.generate_prospect_rankings(limit=1)

            if rankings:
                top_prospect = rankings[0]
                scores = top_prospect['scores']

                print(f"Prospect: {top_prospect['name']}")
                print(f"Position: {top_prospect['position']}")
                print(f"Organization: {top_prospect['organization']}")
                print(f"Age: {top_prospect['age']}")
                print()
                print("Score Breakdown:")
                print(f"  Base FV:              {scores['base_fv']:>6.1f}")
                print(f"  Performance Modifier: {scores['performance_modifier']:>+6.1f}")
                print(f"  Trend Adjustment:     {scores['trend_adjustment']:>+6.1f}")
                print(f"  Age Bonus:            {scores['age_bonus']:>+6.1f}")
                print(f"  " + "-" * 30)
                print(f"  Total Adjustment:     {scores['total_adjustment']:>+6.1f}")
                print(f"  Composite Score:      {scores['composite_score']:>6.1f}")
                print()

                # Tool grades
                tools = top_prospect['tool_grades']
                print("Tool Grades:")
                if top_prospect['position'] not in ['SP', 'RP', 'P']:
                    print(f"  Hit:   {tools.get('hit') or '-'}")
                    print(f"  Power: {tools.get('power') or '-'}")
                    print(f"  Speed: {tools.get('speed') or '-'}")
                    print(f"  Field: {tools.get('field') or '-'}")
                else:
                    print(f"  Fastball: {tools.get('fastball') or '-'}")
                    print(f"  Slider:   {tools.get('slider') or '-'}")
                    print(f"  Curve:    {tools.get('curve') or '-'}")
                    print(f"  Change:   {tools.get('change') or '-'}")
                    print(f"  Command:  {tools.get('command') or '-'}")

                print()

                # Tier classification
                tier_info = await service.get_tier_classification(top_prospect['rank'])
                print(f"Tier: {tier_info['stars']} {tier_info['label']}")
                print()

        except Exception as e:
            print(f"[ERROR] {e}\n")
            import traceback
            traceback.print_exc()

        # Test 4: Test edge cases
        print("\n[TEST 4] Edge Cases & Statistics")
        print("-" * 80)

        try:
            all_rankings = await service.generate_prospect_rankings()

            print(f"Total prospects ranked: {len(all_rankings)}")

            # Count by adjustment type
            hot_count = sum(1 for p in all_rankings if p['scores']['trend_adjustment'] >= 2)
            cold_count = sum(1 for p in all_rankings if p['scores']['trend_adjustment'] <= -2)
            boosted_count = sum(1 for p in all_rankings if p['scores']['total_adjustment'] > 0)
            penalized_count = sum(1 for p in all_rankings if p['scores']['total_adjustment'] < 0)

            print(f"Hot prospects (trending up): {hot_count}")
            print(f"Cold prospects (trending down): {cold_count}")
            print(f"Boosted by adjustments: {boosted_count}")
            print(f"Penalized by adjustments: {penalized_count}")

            # Average adjustments
            avg_adjustment = sum(p['scores']['total_adjustment'] for p in all_rankings) / len(all_rankings)
            print(f"\nAverage total adjustment: {avg_adjustment:+.2f}")

            # FV distribution
            fv_counts = {}
            for p in all_rankings:
                fv = int(p['scores']['base_fv'] / 5) * 5  # Round to nearest 5
                fv_counts[fv] = fv_counts.get(fv, 0) + 1

            print("\nFV Distribution:")
            for fv in sorted(fv_counts.keys(), reverse=True):
                print(f"  FV {fv}: {fv_counts[fv]} prospects")

            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")
            import traceback
            traceback.print_exc()

    await engine.dispose()

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_ranking_service())
