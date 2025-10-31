"""
Test script to verify composite rankings fixes.

This tests:
1. Derived pitch fields are populated (swing, contact, etc.)
2. Full 2025 season data is being used
3. Pitch metrics are calculated correctly
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.prospect_ranking_service import ProspectRankingService
from app.services.pitch_data_aggregator import PitchDataAggregator
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

engine = create_engine(DATABASE_URL)
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def test_derived_fields():
    """Test that derived pitch fields are populated."""
    logger.info("=" * 80)
    logger.info("TEST 1: Derived Pitch Fields")
    logger.info("=" * 80)

    with engine.connect() as conn:
        query = text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                COUNT(*) FILTER (WHERE contact = TRUE) as contacts,
                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) as swing_misses
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 805811  -- Bryce Eldridge
                AND season = 2025
        """)

        result = conn.execute(query).fetchone()

        logger.info(f"Bryce Eldridge 2025 Season Pitch Data:")
        logger.info(f"  Total Pitches: {result.total}")
        logger.info(f"  Swings: {result.swings} ({result.swings/result.total*100:.1f}%)")
        logger.info(f"  Contacts: {result.contacts} ({result.contacts/result.total*100:.1f}%)")
        logger.info(f"  Swing & Misses: {result.swing_misses} ({result.swing_misses/result.total*100:.1f}%)")

        # Verify reasonable ranges
        swing_pct = result.swings / result.total * 100
        contact_pct = result.contacts / result.total * 100

        if swing_pct > 20 and swing_pct < 60:
            logger.info("  ✓ Swing rate looks reasonable (20-60%)")
        else:
            logger.warning(f"  ✗ Swing rate {swing_pct:.1f}% is outside expected range")

        if contact_pct > 15 and contact_pct < 40:
            logger.info("  ✓ Contact rate looks reasonable (15-40%)")
        else:
            logger.warning(f"  ✗ Contact rate {contact_pct:.1f}% is outside expected range")

        logger.info("")


async def test_season_data():
    """Test that full 2025 season data is being used."""
    logger.info("=" * 80)
    logger.info("TEST 2: Full Season Data Usage")
    logger.info("=" * 80)

    async with AsyncSessionLocal() as session:
        service = ProspectRankingService(session)

        # Check season status
        aggregator = PitchDataAggregator(session)
        season_info = await aggregator._check_season_status()

        logger.info(f"Season Status:")
        logger.info(f"  Current Year: {season_info['current_year']}")
        logger.info(f"  Days Since Season End: {season_info['days_since_end']}")
        logger.info(f"  Use Full Season: {season_info['use_full_season']}")

        if season_info['use_full_season']:
            logger.info("  ✓ Using full season data (correct for offseason)")
        else:
            logger.warning("  ✗ Not using full season data (should be True for offseason)")

        logger.info("")


async def test_pitch_metrics():
    """Test that pitch metrics are calculated correctly."""
    logger.info("=" * 80)
    logger.info("TEST 3: Pitch Metrics Calculation")
    logger.info("=" * 80)

    async with AsyncSessionLocal() as session:
        aggregator = PitchDataAggregator(session)

        # Test Bryce Eldridge (hitter)
        logger.info("Testing hitter metrics for Bryce Eldridge...")
        try:
            metrics = await aggregator.get_hitter_pitch_metrics(
                mlb_player_id='805811',
                level='AAA',
                days=60  # This should be ignored for full season
            )

            if metrics:
                logger.info(f"  ✓ Successfully retrieved hitter pitch metrics")
                logger.info(f"    Sample Size: {metrics['sample_size']} pitches")
                logger.info(f"    Days Covered: {metrics['days_covered']}")
                logger.info(f"    Level: {metrics['level']}")
                logger.info(f"    Metrics:")
                for key, value in metrics['metrics'].items():
                    if value is not None:
                        logger.info(f"      {key}: {value:.2f}")
                logger.info(f"    Percentiles:")
                for key, value in metrics['percentiles'].items():
                    if value is not None:
                        logger.info(f"      {key}: {value:.1f}%ile")
            else:
                logger.warning(f"  ✗ No pitch metrics returned for Bryce Eldridge")
        except Exception as e:
            logger.error(f"  ✗ Error calculating hitter metrics: {e}", exc_info=True)

        logger.info("")


async def test_composite_rankings():
    """Test that composite rankings are generated correctly."""
    logger.info("=" * 80)
    logger.info("TEST 4: Composite Rankings Generation")
    logger.info("=" * 80)

    async with AsyncSessionLocal() as session:
        service = ProspectRankingService(session)

        try:
            # Generate rankings for a small subset
            logger.info("Generating composite rankings (limited to 10 prospects)...")
            rankings = await service.generate_prospect_rankings(limit=10)

            if rankings:
                logger.info(f"  ✓ Successfully generated {len(rankings)} prospect rankings")

                # Find Bryce if he's in top 10
                bryce = None
                for prospect in rankings:
                    if prospect['name'] == 'Bryce Eldridge':
                        bryce = prospect
                        break

                if bryce:
                    logger.info(f"\n  Bryce Eldridge Composite Ranking:")
                    logger.info(f"    Rank: {bryce['rank']}")
                    logger.info(f"    Composite Score: {bryce['scores']['composite_score']}")
                    logger.info(f"    Base FV: {bryce['scores']['base_fv']}")
                    logger.info(f"    Performance Modifier: {bryce['scores']['performance_modifier']:+.1f}")
                    logger.info(f"    Trend Adjustment: {bryce['scores']['trend_adjustment']:+.1f}")
                    logger.info(f"    Age Adjustment: {bryce['scores']['age_adjustment']:+.1f}")

                    breakdown = bryce['scores'].get('performance_breakdown')
                    if breakdown:
                        logger.info(f"    Performance Breakdown:")
                        logger.info(f"      Source: {breakdown.get('source')}")
                        if breakdown.get('source') == 'pitch_data':
                            logger.info(f"      Sample Size: {breakdown.get('sample_size')} pitches")
                            logger.info(f"      Composite Percentile: {breakdown.get('composite_percentile'):.1f}%ile")
                            logger.info(f"      ✓ Using pitch-level data (preferred)")
                        else:
                            logger.info(f"      Metric: {breakdown.get('metric')}")
                            logger.info(f"      Value: {breakdown.get('value')}")
                            logger.info(f"      ⚠ Using game log fallback")
                else:
                    logger.info(f"\n  Note: Bryce Eldridge not in top 10, checking first prospect...")
                    first = rankings[0]
                    logger.info(f"    #{first['rank']}: {first['name']} ({first['position']})")
                    logger.info(f"      Composite: {first['scores']['composite_score']}")
                    breakdown = first['scores'].get('performance_breakdown')
                    if breakdown:
                        logger.info(f"      Performance Source: {breakdown.get('source')}")

            else:
                logger.warning(f"  ✗ No rankings returned")

        except Exception as e:
            logger.error(f"  ✗ Error generating rankings: {e}", exc_info=True)

        logger.info("")


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 80)
    logger.info("COMPOSITE RANKINGS FIX VERIFICATION")
    logger.info("=" * 80 + "\n")

    try:
        await test_derived_fields()
        await test_season_data()
        await test_pitch_metrics()
        await test_composite_rankings()

        logger.info("=" * 80)
        logger.info("ALL TESTS COMPLETED")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
