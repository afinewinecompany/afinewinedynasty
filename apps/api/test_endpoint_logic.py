"""Test endpoint logic without running the server."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.prospect_ranking_service import ProspectRankingService
from datetime import datetime

DATABASE_URL = "postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def test_endpoint_logic():
    """Test the endpoint logic directly."""

    print("\n" + "=" * 80)
    print("TESTING COMPOSITE RANKINGS ENDPOINT LOGIC")
    print("=" * 80 + "\n")

    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Initialize service
        service = ProspectRankingService(db)

        # Test 1: Generate full rankings (top 10)
        print("[TEST 1] Generate Rankings (limit=10)")
        print("-" * 80)

        try:
            rankings = await service.generate_prospect_rankings(limit=10)

            print(f"[OK] Generated {len(rankings)} rankings\n")

            # Simulate endpoint response building
            response_prospects = []

            for ranked_prospect in rankings:
                # Get tier classification
                tier_info = await service.get_tier_classification(ranked_prospect['rank'])

                response_prospect = {
                    'rank': ranked_prospect['rank'],
                    'prospect_id': ranked_prospect['prospect_id'],
                    'name': ranked_prospect['name'],
                    'position': ranked_prospect['position'],
                    'organization': ranked_prospect['organization'],
                    'age': ranked_prospect['age'],
                    'level': ranked_prospect['level'],
                    'composite_score': ranked_prospect['scores']['composite_score'],
                    'base_fv': ranked_prospect['scores']['base_fv'],
                    'performance_modifier': ranked_prospect['scores']['performance_modifier'],
                    'trend_adjustment': ranked_prospect['scores']['trend_adjustment'],
                    'age_adjustment': ranked_prospect['scores']['age_adjustment'],
                    'total_adjustment': ranked_prospect['scores']['total_adjustment'],
                    'tool_grades': ranked_prospect['tool_grades'],
                    'tier': tier_info['tier'],
                    'tier_label': tier_info['label']
                }

                response_prospects.append(response_prospect)

            # Display results
            print(f"{'Rank':<5} {'Name':<25} {'Pos':<5} {'Org':<8} {'FV':<6} {'Comp':<6} {'Adj':<6} {'Tier'}")
            print("-" * 95)

            for p in response_prospects:
                print(f"#{p['rank']:<4} {p['name'][:24]:<25} {p['position']:<5} "
                      f"{(p['organization'] or '?')[:7]:<8} "
                      f"{p['base_fv']:<6.1f} {p['composite_score']:<6.1f} "
                      f"{p['total_adjustment']:+5.1f}  {p['tier_label']}")

            print()

            # Test score breakdown detail
            print("Score Breakdown for #1:")
            top = response_prospects[0]
            print(f"  Base FV:         {top['base_fv']:>6.1f}")
            print(f"  Performance:     {top['performance_modifier']:>+6.1f}")
            print(f"  Trend:           {top['trend_adjustment']:>+6.1f}")
            print(f"  Age:             {top['age_adjustment']:>+6.1f}")
            print(f"  ---------------")
            print(f"  Total Adj:       {top['total_adjustment']:>+6.1f}")
            print(f"  Composite:       {top['composite_score']:>6.1f}")
            print()

            # Test tool grades
            print("Tool Grades for #1:")
            for grade_name, grade_value in top['tool_grades'].items():
                if grade_value is not None:
                    print(f"  {grade_name.capitalize():<12} {grade_value}")
            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")
            import traceback
            traceback.print_exc()

        # Test 2: Filter by position
        print("[TEST 2] Filter by Position (SS, limit=5)")
        print("-" * 80)

        try:
            rankings = await service.generate_prospect_rankings(
                position_filter='SS',
                limit=5
            )

            print(f"[OK] Found {len(rankings)} shortstops\n")

            for p in rankings:
                print(f"#{p['rank']:<3} {p['name']:<25} FV: {p['scores']['base_fv']:<5.1f} "
                      f"Comp: {p['scores']['composite_score']:<5.1f}")

            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")

        # Test 3: Pagination simulation
        print("[TEST 3] Pagination (page 1, page_size=5)")
        print("-" * 80)

        try:
            # Get first 20 to test pagination
            all_rankings = await service.generate_prospect_rankings(limit=20)

            # Simulate pagination
            page = 1
            page_size = 5
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            paginated = all_rankings[start_idx:end_idx]

            print(f"Total: {len(all_rankings)}")
            print(f"Page {page}: Showing {len(paginated)} prospects ({start_idx+1}-{end_idx})")
            print()

            for p in paginated:
                print(f"  #{p['rank']} {p['name']}")

            total_pages = (len(all_rankings) + page_size - 1) // page_size
            print(f"\nTotal pages: {total_pages}")
            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")

        # Test 4: Response model completeness check
        print("[TEST 4] Response Model Completeness")
        print("-" * 80)

        try:
            rankings = await service.generate_prospect_rankings(limit=1)
            prospect = rankings[0]
            tier_info = await service.get_tier_classification(prospect['rank'])

            # Check all required fields exist
            required_fields = [
                'rank', 'prospect_id', 'name', 'position', 'organization',
                'age', 'level', 'scores', 'tool_grades'
            ]

            score_fields = [
                'composite_score', 'base_fv', 'performance_modifier',
                'trend_adjustment', 'age_adjustment', 'total_adjustment'
            ]

            missing_main = [f for f in required_fields if f not in prospect]
            missing_scores = [f for f in score_fields if f not in prospect['scores']]

            if not missing_main and not missing_scores:
                print("[OK] All required fields present")
            else:
                if missing_main:
                    print(f"[WARN] Missing main fields: {missing_main}")
                if missing_scores:
                    print(f"[WARN] Missing score fields: {missing_scores}")

            print(f"[OK] Tier classification working: Tier {tier_info['tier']} - {tier_info['label']}")
            print()

        except Exception as e:
            print(f"[ERROR] {e}\n")
            import traceback
            traceback.print_exc()

    await engine.dispose()

    print("=" * 80)
    print("ENDPOINT LOGIC TESTING COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_endpoint_logic())
