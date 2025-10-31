"""
Test the enhanced pitch metrics in the ranking system
"""
import asyncio
import os
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append('app')

# Enable enhanced metrics
os.environ['USE_ENHANCED_METRICS'] = 'true'

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_enhanced_rankings():
    """Test enhanced metrics in rankings"""

    # Create async engine and session
    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        ranking_service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING ENHANCED RANKINGS FOR SPECIFIC PROSPECTS")
        print("=" * 80)

        # Get specific prospects to test
        from sqlalchemy import text

        # Test with prospects we know have good pitch data
        query = text("""
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                p.position,
                p.fangraphs_fv,
                p.current_level,
                p.age,
                p.organization,
                COUNT(DISTINCT bp.game_pk) as pitch_games,
                COUNT(bp.*) as total_pitches
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN ('Jesús Made', 'Bryce Eldridge', 'Konnor Griffin', 'Roman Anthony', 'Kristian Campbell')
            GROUP BY p.id, p.name, p.mlb_player_id, p.position, p.fangraphs_fv, p.current_level, p.age, p.organization
            ORDER BY p.name
        """)

        result = await db.execute(query)
        prospects = result.fetchall()

        for row in prospects:
            prospect_data = {
                'id': row[0],
                'name': row[1],
                'mlb_player_id': row[2],
                'position': row[3],
                'fangraphs_fv': row[4],
                'current_level': row[5],
                'age': row[6],
                'organization': row[7]
            }
            pitch_games = row[8]
            total_pitches = row[9]

            print(f"\n{prospect_data['name']} ({prospect_data['position']}) - {prospect_data['organization']}")
            print(f"  MLB ID: {prospect_data['mlb_player_id']}")
            print(f"  Level: {prospect_data['current_level']}")
            print(f"  FanGraphs FV: {prospect_data['fangraphs_fv']}")
            print(f"  Pitch Data: {total_pitches:,} pitches in {pitch_games} games")
            print("-" * 60)

            # Get recent stats for this prospect
            stats_query = text("""
                SELECT
                    recent_level,
                    recent_games,
                    recent_ops,
                    recent_avg,
                    recent_obp,
                    recent_slg,
                    recent_k_rate,
                    recent_bb_rate
                FROM milb_recent_stats
                WHERE prospect_id = :prospect_id
            """)

            stats_result = await db.execute(stats_query, {'prospect_id': prospect_data['id']})
            recent_stats = stats_result.fetchone()

            if recent_stats:
                recent_stats_dict = {
                    'recent_level': recent_stats[0],
                    'recent_games': recent_stats[1],
                    'recent_ops': recent_stats[2],
                    'recent_avg': recent_stats[3],
                    'recent_obp': recent_stats[4],
                    'recent_slg': recent_stats[5],
                    'recent_k_rate': recent_stats[6],
                    'recent_bb_rate': recent_stats[7]
                }
                print(f"  Recent Stats: {recent_stats_dict['recent_games']} games, OPS: {recent_stats_dict['recent_ops']:.3f}")
            else:
                recent_stats_dict = None
                print("  Recent Stats: Not available")

            # Calculate performance modifier
            is_hitter = prospect_data['position'] not in ['SP', 'RP', 'P']

            try:
                modifier, breakdown = await ranking_service.calculate_performance_modifier(
                    prospect_data,
                    recent_stats_dict,
                    is_hitter
                )

                print(f"\n  Performance Modifier: {modifier:+.1f}")

                if breakdown:
                    print(f"  Data Source: {breakdown.get('source', 'unknown')}")

                    if breakdown['source'] == 'pitch_data':
                        print(f"  Sample Size: {breakdown.get('sample_size', 0)} pitches")
                        print(f"  Composite Percentile: {breakdown.get('composite_percentile', 0):.1f}th")

                        # Show available metrics
                        if 'metrics' in breakdown:
                            available_metrics = [k for k, v in breakdown['metrics'].items() if v is not None]
                            print(f"  Enhanced Metrics Available ({len(available_metrics)}):")
                            for metric in available_metrics[:5]:
                                value = breakdown['metrics'][metric]
                                percentile = breakdown.get('percentiles', {}).get(metric, 50)
                                print(f"    - {metric}: {value:.1f}% ({percentile:.0f}th percentile)")

                        # Show if enhanced
                        if 'enhanced_metrics' in breakdown or len(available_metrics) > 5:
                            print("  ✓ Using ENHANCED metrics (9+ dimensions)")
                        else:
                            print("  Using standard metrics (2-5 dimensions)")

                    elif breakdown['source'] == 'game_logs':
                        print(f"  Fallback to game logs - {breakdown.get('metric')}: {breakdown.get('value', 0):.3f}")

                    else:
                        print(f"  {breakdown.get('note', 'No data available')}")

                # Calculate final composite score
                base_score = prospect_data.get('fangraphs_fv', 45)
                final_score = base_score + modifier

                print(f"\n  Final Composite Score: {final_score:.1f} (Base: {base_score}, Modifier: {modifier:+.1f})")

            except Exception as e:
                print(f"  Error calculating modifier: {e}")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("\nEnhanced metrics provide:")
        print("- More nuanced evaluation with 9+ metrics vs 2-5")
        print("- Count leverage situations (two-strike, first pitch, ahead/behind)")
        print("- Discipline scores and approach metrics")
        print("- In-play rates and productive swing rates")
        print("\nThis gives a more complete picture of player performance")
        print("and should better differentiate prospects in the rankings.")

if __name__ == "__main__":
    asyncio.run(test_enhanced_rankings())