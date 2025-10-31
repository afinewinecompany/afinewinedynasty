"""
Test the enhanced pitch metrics for specific prospects
"""
import psycopg2
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')
from app.services.pitch_data_aggregator_enhanced import EnhancedPitchDataAggregator

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_enhanced_metrics():
    """Test enhanced metrics for key prospects"""

    # Create async engine and session
    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        aggregator = EnhancedPitchDataAggregator(db)

        # Test prospects (name, mlb_id, position, level)
        test_players = [
            ('Jesús Made', '701350', 'Hitter', 'AA'),  # Will need to look up actual ID
            ('Bryce Eldridge', '805811', 'Hitter', 'AAA'),
            ('Konnor Griffin', '804606', 'Hitter', 'AA'),
            ('Roman Anthony', '701350', 'Hitter', 'AA'),  # Actual ID needs lookup
            ('Kristian Campbell', '692225', 'Hitter', 'AA')
        ]

        # First, find Jesús Made's actual ID
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT mlb_player_id, name, position, organization
            FROM prospects
            WHERE name ILIKE '%made%' OR name ILIKE '%jesús%' OR name ILIKE '%jesus%'
            ORDER BY name
        """)

        made_results = cursor.fetchall()
        jesus_made_id = None
        for mlb_id, name, pos, org in made_results:
            if 'Made' in name and ('Jesus' in name or 'Jesús' in name):
                jesus_made_id = mlb_id
                print(f"Found Jesús Made: {name} (ID: {mlb_id})")
                break

        if jesus_made_id:
            test_players[0] = ('Jesús Made', str(jesus_made_id), 'Hitter', 'AA')

        # Also lookup Roman Anthony
        cursor.execute("""
            SELECT mlb_player_id, name, position, organization
            FROM prospects
            WHERE name ILIKE '%roman%' AND name ILIKE '%anthony%'
            ORDER BY name
        """)

        anthony_results = cursor.fetchall()
        if anthony_results:
            roman_id = anthony_results[0][0]
            test_players[3] = ('Roman Anthony', str(roman_id), 'Hitter', 'AA')

        conn.close()

        print("=" * 80)
        print("TESTING ENHANCED PITCH METRICS")
        print("=" * 80)

        for name, mlb_id, player_type, level in test_players:
            print(f"\n{name} (ID: {mlb_id}) - {level}:")
            print("-" * 60)

            try:
                if player_type == 'Hitter':
                    result = await aggregator.get_enhanced_hitter_metrics(mlb_id, level)
                else:
                    result = await aggregator.get_enhanced_pitcher_metrics(mlb_id, level)

                if not result:
                    print("  No data available")
                    continue

                metrics = result['metrics']
                percentiles = result['percentiles']

                print(f"  Sample Size: {result['sample_size']} pitches")
                print(f"  Levels: {result.get('levels_included', [level])}")
                print(f"  Metrics Available: {result['metrics_available']}")

                print("\n  Raw Metrics:")
                for metric, value in metrics.items():
                    if value is not None:
                        print(f"    {metric:25s}: {value:6.2f}%")

                print("\n  Percentiles:")
                for metric, percentile in percentiles.items():
                    if percentile != 50.0:  # Only show non-default values
                        print(f"    {metric:25s}: {percentile:5.1f}th percentile")

                # Calculate composite score
                composite, contributions = await aggregator.calculate_enhanced_composite(
                    percentiles,
                    is_hitter=(player_type == 'Hitter')
                )

                print(f"\n  Composite Score: {composite:.1f}th percentile")

                # Get modifier
                modifier = aggregator.percentile_to_modifier(composite)
                print(f"  Ranking Modifier: {modifier:+.1f}")

                # Show top contributing metrics
                print("\n  Top Contributing Metrics:")
                sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
                for metric, contrib in sorted_contribs[:5]:
                    print(f"    {metric:25s}: {contrib:5.2f} points")

            except Exception as e:
                print(f"  Error: {e}")

        print("\n" + "=" * 80)
        print("COMPARISON: STANDARD vs ENHANCED METRICS")
        print("=" * 80)

        # Compare standard vs enhanced for one player
        if jesus_made_id:
            print(f"\nJesús Made Comparison:")

            # Get standard metrics (from original aggregator)
            from app.services.pitch_data_aggregator import PitchDataAggregator
            standard_agg = PitchDataAggregator(db)

            standard_result = await standard_agg.get_hitter_pitch_metrics(
                str(jesus_made_id), 'AA'
            )

            enhanced_result = await aggregator.get_enhanced_hitter_metrics(
                str(jesus_made_id), 'AA'
            )

            if standard_result and enhanced_result:
                print("\n  Standard Metrics (2 metrics):")
                print(f"    Contact Rate: {standard_result['metrics'].get('contact_rate', 'N/A')}")
                print(f"    Whiff Rate: {standard_result['metrics'].get('whiff_rate', 'N/A')}")

                std_composite, _ = await standard_agg.calculate_weighted_composite(
                    standard_result['percentiles'], is_hitter=True
                )
                print(f"    Composite: {std_composite:.1f}th percentile")
                print(f"    Modifier: {standard_agg.percentile_to_modifier(std_composite):+.1f}")

                print("\n  Enhanced Metrics (9+ metrics):")
                available = [k for k, v in enhanced_result['metrics'].items() if v is not None]
                print(f"    Available Metrics: {', '.join(available[:5])}...")

                enh_composite, _ = await aggregator.calculate_enhanced_composite(
                    enhanced_result['percentiles'], is_hitter=True
                )
                print(f"    Composite: {enh_composite:.1f}th percentile")
                print(f"    Modifier: {aggregator.percentile_to_modifier(enh_composite):+.1f}")

                print(f"\n  Difference: {enh_composite - std_composite:+.1f} percentile points")
                print(f"  More nuanced evaluation with {len(available)} metrics vs 2")

if __name__ == "__main__":
    asyncio.run(test_enhanced_metrics())