"""
Test the full ranking calculation with pitch data to diagnose the issue
"""
import asyncio
from app.db.database import AsyncSessionLocal
from app.services.prospect_ranking_service import ProspectRankingService
from app.services.pitch_data_aggregator import PitchDataAggregator
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_ranking_calculation():
    """Test ranking calculation for specific prospects"""

    print("="*80)
    print("TESTING RANKING CALCULATION WITH PITCH DATA")
    print("="*80)

    async with AsyncSessionLocal() as db:
        # Initialize services
        ranking_service = ProspectRankingService(db)
        pitch_aggregator = PitchDataAggregator(db)

        # Test prospects with known pitch data
        test_cases = [
            {'name': 'Bryce Eldridge', 'mlb_id': '805811', 'position': '1B', 'level': 'AAA'},
            {'name': 'Konnor Griffin', 'mlb_id': '804606', 'position': 'SS', 'level': 'AA'},
        ]

        for test_case in test_cases:
            print(f"\n{'-'*80}")
            print(f"Testing: {test_case['name']}")
            print(f"{'-'*80}")

            # Test pitch data retrieval
            print(f"\n1. Testing pitch data retrieval:")
            try:
                pitch_metrics = await pitch_aggregator.get_hitter_pitch_metrics(
                    test_case['mlb_id'],
                    test_case['level'],
                    days=60
                )

                if pitch_metrics:
                    print(f"   SUCCESS: Got pitch metrics")
                    print(f"   - Sample size: {pitch_metrics.get('sample_size', 0)} pitches")
                    print(f"   - Metrics: {list(pitch_metrics.get('metrics', {}).keys())}")
                    print(f"   - Percentiles: {list(pitch_metrics.get('percentiles', {}).keys())}")
                else:
                    print(f"   FAILED: No pitch metrics returned")
                    print(f"   This would cause fallback to game logs!")

            except Exception as e:
                print(f"   ERROR: {e}")
                print(f"   This error causes fallback to game logs!")

            # Create a mock prospect data for testing
            print(f"\n2. Testing performance modifier calculation:")

            prospect_data = {
                'name': test_case['name'],
                'mlb_player_id': test_case['mlb_id'],
                'position': test_case['position'],
                'current_level': test_case['level'],
                'recent_level': test_case['level'],
                'fangraphs_fv': 55.0
            }

            recent_stats = {
                'recent_ops': 0.800,
                'recent_games': 50,
                'recent_level': test_case['level']
            }

            try:
                performance_mod, breakdown = await ranking_service.calculate_performance_modifier(
                    prospect_data,
                    recent_stats,
                    is_hitter=True
                )

                print(f"   Performance Modifier: {performance_mod:+.1f}")
                if breakdown:
                    print(f"   Source: {breakdown.get('source', 'unknown')}")
                    if breakdown.get('source') == 'pitch_data':
                        print(f"   PITCH DATA USED!")
                        print(f"   - Composite percentile: {breakdown.get('composite_percentile', 0):.1f}%")
                        print(f"   - Sample size: {breakdown.get('sample_size', 0)} pitches")
                    else:
                        print(f"   GAME LOG FALLBACK USED (not pitch data)")

            except Exception as e:
                print(f"   ERROR in performance modifier: {e}")

        # Now test the full ranking generation
        print(f"\n{'='*80}")
        print("3. Testing full ranking generation:")
        print(f"{'='*80}")

        try:
            rankings = await ranking_service.generate_prospect_rankings(limit=5)

            print(f"\nTop 5 Rankings:")
            for i, prospect in enumerate(rankings[:5], 1):
                print(f"\n{i}. {prospect['name']} ({prospect['position']})")
                scores = prospect.get('scores', {})
                print(f"   Composite: {scores.get('composite_score', 0):.1f}")
                print(f"   Performance Mod: {scores.get('performance_modifier', 0):+.1f}")

                # Check if performance breakdown exists
                perf_breakdown = scores.get('performance_breakdown')
                if perf_breakdown:
                    source = perf_breakdown.get('source', 'unknown')
                    print(f"   Data Source: {source}")
                    if source == 'pitch_data':
                        print(f"   ✓ USING PITCH DATA")
                    else:
                        print(f"   ✗ Using game log fallback")
                else:
                    print(f"   ✗ No performance breakdown")

        except Exception as e:
            print(f"\nERROR in ranking generation: {e}")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(test_ranking_calculation())