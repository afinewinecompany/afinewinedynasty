"""
Test Composite Rankings with Pitch Metrics Enabled

This validates that pitch metrics are properly integrated into the
prospect ranking system after re-enabling them.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import sys
sys.path.append('app')

from app.services.prospect_ranking_service import ProspectRankingService

ASYNC_DB_URL = 'postgresql+asyncpg://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_rankings_with_pitch_metrics():
    """Test composite rankings with pitch metrics enabled"""

    engine = create_async_engine(ASYNC_DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        ranking_service = ProspectRankingService(db)

        print("=" * 80)
        print("TESTING COMPOSITE RANKINGS WITH PITCH METRICS ENABLED")
        print("=" * 80)

        # First, get prospects we know have pitch data
        query = text("""
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                p.position,
                p.fangraphs_fv,
                p.current_level,
                COUNT(DISTINCT bp.game_pk) as pitch_games,
                COUNT(bp.*) as total_pitches
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN ('Jesus Made', 'Roman Anthony', 'Kristian Campbell')
            GROUP BY p.id, p.name, p.mlb_player_id, p.position, p.fangraphs_fv, p.current_level
            ORDER BY p.name
        """)

        result = await db.execute(query)
        test_prospects = result.fetchall()

        print(f"\nFound {len(test_prospects)} test prospects with pitch data\n")

        for row in test_prospects:
            prospect_data = {
                'id': row[0],
                'name': row[1],
                'mlb_player_id': row[2],
                'position': row[3],
                'fangraphs_fv': row[4],
                'current_level': row[5]
            }
            pitch_games = row[6]
            total_pitches = row[7]

            print(f"{prospect_data['name']} ({prospect_data['position']}):")
            print(f"  Base FV: {prospect_data['fangraphs_fv']}")
            print(f"  Level: {prospect_data['current_level']}")
            print(f"  Pitch Data: {total_pitches:,} pitches in {pitch_games} games")
            print("-" * 60)

            try:
                # Get recent stats
                stats_query = text("""
                    SELECT
                        recent_level,
                        recent_games,
                        recent_ops,
                        recent_k_rate,
                        recent_bb_rate
                    FROM milb_recent_stats
                    WHERE prospect_id = :prospect_id
                """)

                stats_result = await db.execute(stats_query, {'prospect_id': prospect_data['id']})
                recent_stats_row = stats_result.fetchone()

                if recent_stats_row:
                    recent_stats = {
                        'recent_level': recent_stats_row[0],
                        'recent_games': recent_stats_row[1],
                        'recent_ops': recent_stats_row[2],
                        'recent_k_rate': recent_stats_row[3],
                        'recent_bb_rate': recent_stats_row[4]
                    }
                else:
                    recent_stats = None

                # Calculate performance modifier
                is_hitter = prospect_data['position'] not in ['SP', 'RP', 'P']

                modifier, breakdown = await ranking_service.calculate_performance_modifier(
                    prospect_data,
                    recent_stats,
                    is_hitter
                )

                print(f"  Performance Modifier: {modifier:+.1f}")

                if breakdown:
                    print(f"  Data Source: {breakdown.get('source', 'unknown')}")

                    if breakdown['source'] == 'pitch_data':
                        print(f"  SUCCESS - Using Pitch Metrics!")
                        print(f"  Sample Size: {breakdown.get('sample_size', 0)} pitches")
                        print(f"  Composite Percentile: {breakdown.get('composite_percentile', 0):.1f}th")

                        # Show metrics
                        if 'metrics' in breakdown:
                            metrics = breakdown['metrics']
                            percentiles = breakdown.get('percentiles', {})

                            print(f"\n  Available Pitch Metrics:")
                            for metric_name, value in metrics.items():
                                if value is not None:
                                    percentile = percentiles.get(metric_name, 50)
                                    print(f"    - {metric_name}: {value:.1f} ({percentile:.0f}th percentile)")

                    elif breakdown['source'] == 'game_logs':
                        print(f"  FALLBACK - Using Game Logs (pitch data not available)")
                        print(f"  Metric: {breakdown.get('metric')} = {breakdown.get('value', 0):.3f}")

                    else:
                        print(f"  WARNING - No performance data available")

                # Calculate final composite score
                base_score = prospect_data.get('fangraphs_fv', 45)
                final_score = base_score + modifier

                print(f"\n  Final Composite Score: {final_score:.1f}")
                print(f"  (Base: {base_score}, Modifier: {modifier:+.1f})")
                print()

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
                print()

        # Now test full rankings generation (small sample)
        print("\n" + "=" * 80)
        print("TESTING FULL RANKINGS GENERATION (TOP 10)")
        print("=" * 80)

        try:
            rankings = await ranking_service.generate_prospect_rankings(limit=10)

            print(f"\nGenerated {len(rankings)} rankings successfully!\n")

            # Count how many used pitch data
            pitch_data_count = 0
            for ranking in rankings:
                if ranking.get('pitch_metrics_used'):
                    pitch_data_count += 1

            print(f"Prospects with pitch metrics: {pitch_data_count}/{len(rankings)}\n")

            # Show top 5
            print("Top 5 Prospects:")
            for i, prospect in enumerate(rankings[:5], 1):
                data_source = "Pitch Data" if prospect.get('pitch_metrics_used') else "Game Logs"
                print(f"  {i}. {prospect['name']:25s} {prospect['composite_score']:5.1f} ({data_source})")

        except Exception as e:
            print(f"\nERROR generating full rankings: {e}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_rankings_with_pitch_metrics())
