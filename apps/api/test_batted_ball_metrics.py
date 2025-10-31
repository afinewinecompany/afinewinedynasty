"""
Test the comprehensive batted ball metrics
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

from app.services.pitch_data_aggregator_with_batted_balls import BattedBallPitchDataAggregator

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_batted_ball_metrics():
    """Test comprehensive batted ball metrics"""

    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        aggregator = BattedBallPitchDataAggregator(db)

        # Test with Jesús Made who we know has good batted ball data
        print("=" * 80)
        print("TESTING COMPREHENSIVE BATTED BALL METRICS")
        print("=" * 80)

        test_players = [
            ('Jesús Made', '815908', 'AA'),
            ('Roman Anthony', '701350', 'AAA'),
            ('Kristian Campbell', '692225', 'AAA')
        ]

        for name, mlb_id, level in test_players:
            print(f"\n{name} (ID: {mlb_id}) - {level}:")
            print("-" * 60)

            result = await aggregator.get_comprehensive_hitter_metrics(mlb_id, level)

            if not result:
                print("  No data available")
                continue

            metrics = result['metrics']
            percentiles = result['percentiles']

            print(f"  Sample Size: {result['sample_size']} pitches, {result['balls_in_play']} balls in play")
            print(f"  Batted Ball Data Coverage:")
            bb_data = result['batted_ball_data']
            print(f"    With trajectory: {bb_data['with_trajectory']}")
            print(f"    With hardness: {bb_data['with_hardness']}")
            print(f"    With hit location: {bb_data['with_hit_location']}")

            print(f"\n  Batted Ball Profile:")
            if metrics.get('ground_ball_rate') is not None:
                print(f"    Ground Ball%: {metrics['ground_ball_rate']:.1f}%")
            if metrics.get('line_drive_rate') is not None:
                print(f"    Line Drive%: {metrics['line_drive_rate']:.1f}%")
            if metrics.get('fly_ball_rate') is not None:
                print(f"    Fly Ball%: {metrics['fly_ball_rate']:.1f}%")
            if metrics.get('popup_rate') is not None:
                print(f"    Pop Up%: {metrics['popup_rate']:.1f}%")

            print(f"\n  Contact Quality:")
            if metrics.get('hard_hit_rate') is not None:
                print(f"    Hard Hit%: {metrics['hard_hit_rate']:.1f}%")
            if metrics.get('soft_hit_rate') is not None:
                print(f"    Soft Hit%: {metrics['soft_hit_rate']:.1f}%")

            print(f"\n  Spray Chart:")
            if metrics.get('pull_rate') is not None:
                print(f"    Pull%: {metrics['pull_rate']:.1f}%")
            if metrics.get('center_rate') is not None:
                print(f"    Center%: {metrics['center_rate']:.1f}%")
            if metrics.get('oppo_rate') is not None:
                print(f"    Oppo%: {metrics['oppo_rate']:.1f}%")

            print(f"\n  Power Indicators:")
            if metrics.get('pull_fly_ball_rate') is not None:
                print(f"    Pull Fly Ball%: {metrics['pull_fly_ball_rate']:.1f}% (of all fly balls)")
            if metrics.get('spray_ability') is not None:
                print(f"    Spray Ability Score: {metrics['spray_ability']:.1f}/100")

            print(f"\n  Approach Metrics:")
            if metrics.get('contact_rate') is not None:
                print(f"    Contact%: {metrics['contact_rate']:.1f}%")
            if metrics.get('whiff_rate') is not None:
                print(f"    Whiff%: {metrics['whiff_rate']:.1f}%")
            if metrics.get('two_strike_contact_rate') is not None:
                print(f"    Two-Strike Contact%: {metrics['two_strike_contact_rate']:.1f}%")
            if metrics.get('discipline_score') is not None:
                print(f"    Discipline Score: {metrics['discipline_score']:.1f}/100")

            # Calculate composite
            composite, contributions = await aggregator.calculate_comprehensive_composite(
                percentiles, is_hitter=True
            )

            print(f"\n  Composite Score: {composite:.1f}th percentile")
            modifier = aggregator.percentile_to_modifier(composite)
            print(f"  Ranking Modifier: {modifier:+.1f}")

            print(f"\n  Top Contributing Metrics:")
            sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
            for metric, contrib in sorted_contribs[:5]:
                percentile = percentiles.get(metric, 50.0)
                print(f"    {metric:25s}: {contrib:5.2f} pts ({percentile:.0f}th percentile)")

        print("\n" + "=" * 80)
        print("COMPREHENSIVE METRICS SUMMARY")
        print("=" * 80)
        print("\nThe comprehensive batted ball metrics now include:")
        print("- Batted Ball Types (GB%, LD%, FB%, PU%)")
        print("- Contact Quality (Hard%, Soft%)")
        print("- Spray Angles (Pull%, Center%, Oppo%)")
        print("- Power Indicators (Pull Fly Ball%)")
        print("- Spray Ability Score (balance metric)")
        print("\nThese provide crucial insights into:")
        print("1. Hitting approach and style")
        print("2. Power potential (fly balls + pull tendency)")
        print("3. Contact quality and consistency")
        print("4. Ability to use all fields")
        print("\nThis creates a much more complete picture than just contact/whiff rates!")

if __name__ == "__main__":
    asyncio.run(test_batted_ball_metrics())