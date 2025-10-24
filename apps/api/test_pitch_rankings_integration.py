"""
Test that rankings are using pitch-level data for prospects with available data.
"""
import asyncio
from sqlalchemy import text
from app.db.database import get_db_sync
from app.services.prospect_ranking_service import ProspectRankingService
from app.services.pitch_data_aggregator import PitchDataAggregator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pitch_integration():
    """Test pitch data integration for key prospects."""

    print("="*80)
    print("TESTING PITCH DATA INTEGRATION IN RANKINGS")
    print("="*80)

    # Get async db session
    from app.db.database import AsyncSessionLocal
    db = AsyncSessionLocal()

    try:
        # Test prospects
        test_prospects = [
            'Bryce Eldridge',
            'Konnor Griffin',
            'Roman Anthony',
            'Kristian Campbell'
        ]

        for prospect_name in test_prospects:
            print(f"\n{'-'*80}")
            print(f"Testing: {prospect_name}")
            print(f"{'-'*80}")

            # Get prospect data
            query = text("""
                SELECT
                    p.id,
                    p.name,
                    p.position,
                    p.mlb_player_id,
                    p.current_level,
                    COALESCE(h.fv, pit.fv) as fangraphs_fv
                FROM prospects p
                LEFT JOIN fangraphs_hitter_grades h
                    ON p.fg_player_id = h.fangraphs_player_id
                    AND h.data_year = 2025
                LEFT JOIN fangraphs_pitcher_grades pit
                    ON p.fg_player_id = pit.fangraphs_player_id
                    AND pit.data_year = 2025
                WHERE p.name = :name
                LIMIT 1
            """)

            result = await db.execute(query, {"name": prospect_name})
            row = result.fetchone()

            if not row:
                print(f"  Prospect not found in database")
                continue

            prospect_id, name, position, mlb_player_id, level, fv = row
            is_hitter = position not in ['SP', 'RP', 'P']

            print(f"  Position: {position} ({'Hitter' if is_hitter else 'Pitcher'})")
            print(f"  MLB ID: {mlb_player_id}")
            print(f"  Level: {level}")
            print(f"  Base FV: {fv}")

            if not mlb_player_id or not level:
                print(f"  Missing MLB ID or level - skipping")
                continue

            # Check for pitch data
            aggregator = PitchDataAggregator(db)

            if is_hitter:
                pitch_metrics = await aggregator.get_hitter_pitch_metrics(
                    int(mlb_player_id), level, days=60
                )
            else:
                pitch_metrics = await aggregator.get_pitcher_pitch_metrics(
                    int(mlb_player_id), level, days=60
                )

            if pitch_metrics:
                print(f"\n  PITCH DATA AVAILABLE:")
                print(f"    Sample Size: {pitch_metrics['sample_size']} pitches")
                print(f"    Days Covered: {pitch_metrics['days_covered']} days")
                print(f"    Level: {pitch_metrics['level']}")

                print(f"\n  Metrics:")
                for metric, value in pitch_metrics['metrics'].items():
                    print(f"    {metric}: {value:.3f}")

                print(f"\n  Percentiles:")
                for metric, percentile in pitch_metrics['percentiles'].items():
                    print(f"    {metric}: {percentile:.1f}%ile")

                # Calculate weighted composite
                composite, contributions = await aggregator.calculate_weighted_composite(
                    pitch_metrics['percentiles'],
                    is_hitter,
                    ops_percentile=50.0,  # Placeholder
                    k_minus_bb_percentile=50.0  # Placeholder
                )

                print(f"\n  COMPOSITE PERCENTILE: {composite:.1f}%ile")
                print(f"  Weighted Contributions:")
                for metric, weight in contributions.items():
                    print(f"    {metric}: {weight:.1%}")

                # Convert to modifier
                modifier = aggregator.percentile_to_modifier(composite)
                print(f"\n  PERFORMANCE MODIFIER: {modifier:+.1f}")
                print(f"  ADJUSTED SCORE: {fv + modifier:.1f}")

            else:
                print(f"\n  NO PITCH DATA AVAILABLE")
                print(f"  Rankings will use game log fallback")

        print(f"\n{'='*80}")
        print("TEST COMPLETE")
        print(f"{'='*80}")

        # Check overall pitch data availability
        print(f"\nOVERALL PITCH DATA STATUS:")

        # Count prospects with pitch data
        query = text("""
            SELECT
                COUNT(DISTINCT CASE WHEN p.position NOT IN ('SP', 'RP') THEN bp.mlb_batter_id END) as batters_with_data,
                COUNT(DISTINCT CASE WHEN p.position IN ('SP', 'RP') THEN pp.mlb_pitcher_id END) as pitchers_with_data,
                COUNT(DISTINCT p.id) as total_prospects
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp
                ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            LEFT JOIN milb_pitcher_pitches pp
                ON p.mlb_player_id::integer = pp.mlb_pitcher_id
                AND pp.season = 2025
            WHERE p.mlb_player_id IS NOT NULL
        """)

        result = await db.execute(query)
        row = result.fetchone()

        if row:
            batters, pitchers, total = row
            print(f"  Batters with pitch data: {batters}")
            print(f"  Pitchers with pitch data: {pitchers}")
            print(f"  Total prospects: {total}")
            print(f"  Coverage: {((batters + pitchers) / total * 100):.1f}%")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(test_pitch_integration())
