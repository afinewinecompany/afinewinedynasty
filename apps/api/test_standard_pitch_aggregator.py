"""
Test Standard Pitch Aggregator in isolation to verify it works
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

from app.services.pitch_data_aggregator import PitchDataAggregator

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_standard_aggregator():
    """Test standard pitch aggregator with known prospects"""

    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        aggregator = PitchDataAggregator(db)

        print("=" * 80)
        print("TESTING STANDARD PITCH DATA AGGREGATOR")
        print("=" * 80)

        # Test with prospects we know have pitch data
        test_players = [
            ('Jesús Made', '815908', 'AA'),
            ('Roman Anthony', '701350', 'AAA'),
            ('Kristian Campbell', '692225', 'AAA')
        ]

        for name, mlb_id, level in test_players:
            print(f"\n{name} (ID: {mlb_id}) - {level}:")
            print("-" * 60)

            try:
                result = await aggregator.get_hitter_pitch_metrics(mlb_id, level)

                if not result:
                    print("  No data available")
                    continue

                print(f"  SUCCESS!")
                print(f"  Sample Size: {result['sample_size']} pitches")
                print(f"  Metrics Available: {result['metrics_available']}")
                print(f"  Level: {result['level']}")

                metrics = result['metrics']
                percentiles = result['percentiles']

                print(f"\n  Metrics:")
                if metrics.get('exit_velo_90th'):
                    print(f"    Exit Velo (90th): {metrics['exit_velo_90th']:.1f} mph ({percentiles.get('exit_velo_90th', 50):.0f}th percentile)")
                if metrics.get('hard_hit_rate'):
                    print(f"    Hard Hit%: {metrics['hard_hit_rate']:.1f}% ({percentiles.get('hard_hit_rate', 50):.0f}th percentile)")
                if metrics.get('contact_rate'):
                    print(f"    Contact%: {metrics['contact_rate']:.1f}% ({percentiles.get('contact_rate', 50):.0f}th percentile)")
                if metrics.get('whiff_rate'):
                    print(f"    Whiff%: {metrics['whiff_rate']:.1f}% ({percentiles.get('whiff_rate', 50):.0f}th percentile)")
                if metrics.get('chase_rate'):
                    print(f"    Chase%: {metrics['chase_rate']:.1f}% ({percentiles.get('chase_rate', 50):.0f}th percentile)")

                # Calculate composite
                composite, contributions = await aggregator.calculate_weighted_composite(
                    percentiles, is_hitter=True
                )

                print(f"\n  Composite Score: {composite:.1f}th percentile")
                modifier = aggregator.percentile_to_modifier(composite)
                print(f"  Ranking Modifier: {modifier:+.1f}")

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_standard_aggregator())
