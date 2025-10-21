"""
Test script for pitch-based ranking system.

Tests:
1. Materialized view refresh
2. PitchDataAggregator functionality
3. ProspectRankingService integration
4. End-to-end ranking generation
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.services.pitch_data_aggregator import PitchDataAggregator
from app.services.prospect_ranking_service import ProspectRankingService


# Database connection
DATABASE_URL = "postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def refresh_materialized_views(session: AsyncSession):
    """Refresh materialized views to populate with latest data."""
    print("\n" + "=" * 80)
    print("STEP 1: REFRESHING MATERIALIZED VIEWS")
    print("=" * 80)

    try:
        print("\nRefreshing mv_hitter_percentiles_by_level...")
        await session.execute(text("REFRESH MATERIALIZED VIEW mv_hitter_percentiles_by_level;"))
        print("[OK] Hitter percentiles refreshed")

        print("\nRefreshing mv_pitcher_percentiles_by_level...")
        await session.execute(text("REFRESH MATERIALIZED VIEW mv_pitcher_percentiles_by_level;"))
        print("[OK] Pitcher percentiles refreshed")

        await session.commit()

        return True
    except Exception as e:
        print(f"[FAIL] Error refreshing views: {e}")
        return False


async def verify_materialized_views(session: AsyncSession):
    """Verify materialized views contain data."""
    print("\n" + "=" * 80)
    print("STEP 2: VERIFYING MATERIALIZED VIEWS")
    print("=" * 80)

    # Check hitter percentiles
    print("\nChecking hitter percentiles...")
    result = await session.execute(text("""
        SELECT level, season, cohort_size
        FROM mv_hitter_percentiles_by_level
        ORDER BY season DESC, level
    """))

    hitter_rows = result.fetchall()

    if hitter_rows:
        print(f"[OK] Found {len(hitter_rows)} level/season combinations for hitters:")
        for row in hitter_rows:
            print(f"  - {row[0]} ({row[1]}): {row[2]} players")
    else:
        print("[FAIL] No hitter percentile data found")
        return False

    # Check pitcher percentiles
    print("\nChecking pitcher percentiles...")
    result = await session.execute(text("""
        SELECT level, season, cohort_size
        FROM mv_pitcher_percentiles_by_level
        ORDER BY season DESC, level
    """))

    pitcher_rows = result.fetchall()

    if pitcher_rows:
        print(f"[OK] Found {len(pitcher_rows)} level/season combinations for pitchers:")
        for row in pitcher_rows:
            print(f"  - {row[0]} ({row[1]}): {row[2]} players")
    else:
        print("[FAIL] No pitcher percentile data found")
        return False

    return True


async def test_pitch_data_aggregator(session: AsyncSession):
    """Test PitchDataAggregator with real data."""
    print("\n" + "=" * 80)
    print("STEP 3: TESTING PITCH DATA AGGREGATOR")
    print("=" * 80)

    aggregator = PitchDataAggregator(session)

    # Find a prospect with pitch data (hitter)
    print("\nFinding a hitter with pitch data...")
    result = await session.execute(text("""
        SELECT DISTINCT
            p.mlb_player_id,
            p.name,
            p.position,
            bp.level,
            COUNT(*) as pitches
        FROM prospects p
        JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
        WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days'
            AND p.position NOT IN ('SP', 'RP', 'P', 'RHP', 'LHP')
        GROUP BY p.mlb_player_id, p.name, p.position, bp.level
        HAVING COUNT(*) >= 50
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """))

    hitter_row = result.fetchone()

    if hitter_row:
        mlb_player_id, name, position, level, pitches = hitter_row
        print(f"[OK] Testing with {name} ({position}) - {pitches} pitches at {level}")

        # Get pitch metrics
        metrics = await aggregator.get_hitter_pitch_metrics(
            str(mlb_player_id), level, days=60
        )

        if metrics:
            print(f"\n[OK] Successfully retrieved metrics:")
            print(f"  Sample size: {metrics['sample_size']} pitches")
            print(f"  Level: {metrics['level']}")
            print(f"\n  Raw Metrics:")
            for metric, value in metrics['metrics'].items():
                if value is not None:
                    print(f"    {metric}: {value:.2f}")

            print(f"\n  Percentiles:")
            for metric, percentile in metrics['percentiles'].items():
                print(f"    {metric}: {percentile:.1f}%ile")

            # Calculate weighted composite
            composite, contributions = await aggregator.calculate_weighted_composite(
                metrics['percentiles'],
                is_hitter=True
            )

            print(f"\n  Weighted Composite: {composite:.1f}%ile")
            print(f"  Performance Modifier: {aggregator.percentile_to_modifier(composite):+.1f}")

            print(f"\n  Weighted Contributions:")
            for metric, contribution in contributions.items():
                print(f"    {metric}: {contribution:.2f}")
        else:
            print(f"[FAIL] Could not retrieve metrics for {name}")
            return False
    else:
        print("[FAIL] No hitters with sufficient pitch data found")
        return False

    # Find a prospect with pitch data (pitcher)
    print("\n" + "-" * 80)
    print("Finding a pitcher with pitch data...")
    result = await session.execute(text("""
        SELECT DISTINCT
            p.mlb_player_id,
            p.name,
            p.position,
            pp.level,
            COUNT(*) as pitches
        FROM prospects p
        JOIN milb_pitcher_pitches pp ON p.mlb_player_id::integer = pp.mlb_pitcher_id
        WHERE pp.game_date >= CURRENT_DATE - INTERVAL '60 days'
            AND p.position IN ('SP', 'RP', 'P', 'RHP', 'LHP')
        GROUP BY p.mlb_player_id, p.name, p.position, pp.level
        HAVING COUNT(*) >= 100
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """))

    pitcher_row = result.fetchone()

    if pitcher_row:
        mlb_player_id, name, position, level, pitches = pitcher_row
        print(f"[OK] Testing with {name} ({position}) - {pitches} pitches at {level}")

        # Get pitch metrics
        metrics = await aggregator.get_pitcher_pitch_metrics(
            str(mlb_player_id), level, days=60
        )

        if metrics:
            print(f"\n[OK] Successfully retrieved metrics:")
            print(f"  Sample size: {metrics['sample_size']} pitches")
            print(f"  Level: {metrics['level']}")
            print(f"\n  Raw Metrics:")
            for metric, value in metrics['metrics'].items():
                if value is not None:
                    print(f"    {metric}: {value:.2f}")

            print(f"\n  Percentiles:")
            for metric, percentile in metrics['percentiles'].items():
                print(f"    {metric}: {percentile:.1f}%ile")

            # Calculate weighted composite
            composite, contributions = await aggregator.calculate_weighted_composite(
                metrics['percentiles'],
                is_hitter=False
            )

            print(f"\n  Weighted Composite: {composite:.1f}%ile")
            print(f"  Performance Modifier: {aggregator.percentile_to_modifier(composite):+.1f}")

            print(f"\n  Weighted Contributions:")
            for metric, contribution in contributions.items():
                print(f"    {metric}: {contribution:.2f}")
        else:
            print(f"[FAIL] Could not retrieve metrics for {name}")
            return False
    else:
        print("[FAIL] No pitchers with sufficient pitch data found")
        return False

    return True


async def test_ranking_service_integration(session: AsyncSession):
    """Test ProspectRankingService with pitch data integration."""
    print("\n" + "=" * 80)
    print("STEP 4: TESTING RANKING SERVICE INTEGRATION")
    print("=" * 80)

    ranking_service = ProspectRankingService(session)

    # Get a few prospects with FanGraphs grades
    print("\nGenerating sample rankings (top 10)...")

    try:
        rankings = await ranking_service.generate_prospect_rankings(limit=10)

        if rankings:
            print(f"\n[OK] Successfully generated rankings for {len(rankings)} prospects:")
            print(f"\n{'Rank':<5} {'Name':<25} {'Pos':<4} {'FV':<5} {'Comp':<5} {'Perf Mod':<9} {'Source'}")
            print("-" * 80)

            for prospect in rankings:
                name = prospect['name'][:24]
                pos = prospect['position']
                fv = prospect['scores']['base_fv']
                comp = prospect['scores']['composite_score']
                perf_mod = prospect['scores']['performance_modifier']

                # Check if performance breakdown exists
                breakdown = prospect['scores'].get('performance_breakdown')
                source = breakdown['source'] if breakdown else 'N/A'

                print(f"{prospect['rank']:<5} {name:<25} {pos:<4} {fv:<5.1f} {comp:<5.1f} {perf_mod:+8.1f}  {source}")

            # Show detailed breakdown for first prospect with pitch data
            print("\n" + "-" * 80)
            print("DETAILED BREAKDOWN (First prospect with pitch data):")
            print("-" * 80)

            for prospect in rankings:
                breakdown = prospect['scores'].get('performance_breakdown')
                if breakdown and breakdown.get('source') == 'pitch_data':
                    print(f"\n{prospect['name']} ({prospect['position']}) - Rank #{prospect['rank']}")
                    print(f"Base FV: {prospect['scores']['base_fv']}")
                    print(f"Composite Score: {prospect['scores']['composite_score']}")
                    print(f"\nPerformance Breakdown:")
                    print(f"  Source: {breakdown['source']}")
                    print(f"  Composite Percentile: {breakdown['composite_percentile']:.1f}%ile")
                    print(f"  Sample Size: {breakdown['sample_size']} pitches")
                    print(f"  Days Covered: {breakdown['days_covered']}")
                    print(f"  Level: {breakdown['level']}")

                    print(f"\n  Raw Metrics:")
                    for metric, value in breakdown['metrics'].items():
                        if value is not None:
                            print(f"    {metric}: {value:.2f}")

                    print(f"\n  Percentiles:")
                    for metric, percentile in breakdown['percentiles'].items():
                        print(f"    {metric}: {percentile:.1f}%ile")

                    print(f"\n  Weighted Contributions:")
                    for metric, contribution in breakdown['weighted_contributions'].items():
                        print(f"    {metric}: {contribution:.2f}")

                    break

            return True
        else:
            print("[FAIL] No rankings generated")
            return False

    except Exception as e:
        print(f"[FAIL] Error generating rankings: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PITCH-BASED RANKING SYSTEM TEST SUITE")
    print("=" * 80)

    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Step 1: Refresh materialized views
        success = await refresh_materialized_views(session)
        if not success:
            print("\n[FAIL] FAILED: Could not refresh materialized views")
            return False

        # Step 2: Verify materialized views
        success = await verify_materialized_views(session)
        if not success:
            print("\n[FAIL] FAILED: Materialized views verification failed")
            return False

        # Step 3: Test PitchDataAggregator
        success = await test_pitch_data_aggregator(session)
        if not success:
            print("\n[FAIL] FAILED: PitchDataAggregator test failed")
            return False

        # Step 4: Test RankingService integration
        success = await test_ranking_service_integration(session)
        if not success:
            print("\n[FAIL] FAILED: RankingService integration test failed")
            return False

    print("\n" + "=" * 80)
    print("[OK] ALL TESTS PASSED!")
    print("=" * 80)
    print("\nThe pitch-based ranking system is working correctly!")
    print("\nNext steps:")
    print("1. Set up cron job for daily materialized view refresh")
    print("2. Update API endpoint to include performance_breakdown in responses")
    print("3. Update frontend to display detailed metrics")
    print("4. Monitor performance and gather user feedback")

    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
