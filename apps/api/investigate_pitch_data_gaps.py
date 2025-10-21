"""
Investigate pitch-by-pitch data collection gaps for top prospects.
"""

import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal


async def investigate_specific_prospects():
    """Check pitch data for specific prospects with known gaps."""

    async with AsyncSessionLocal() as db:
        # Check Konnor Griffin and Bryce Eldridge
        query = text("""
            SELECT
                p.name,
                p.mlb_player_id,
                p.position,
                p.current_level,
                p.fg_player_id,
                COUNT(DISTINCT bp.pitch_id) as batter_pitches,
                COUNT(DISTINCT bp.game_date) as batter_games,
                STRING_AGG(DISTINCT bp.level::text, ', ' ORDER BY bp.level::text) as batter_levels,
                MIN(bp.game_date) as first_batter_pitch,
                MAX(bp.game_date) as last_batter_pitch
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id
            WHERE p.name IN ('Konnor Griffin', 'Bryce Eldridge')
            GROUP BY p.name, p.mlb_player_id, p.position, p.current_level, p.fg_player_id
            ORDER BY p.name
        """)

        result = await db.execute(query)
        rows = result.fetchall()

        print("\n" + "="*80)
        print("SPECIFIC PROSPECT INVESTIGATION")
        print("="*80)

        for row in rows:
            print(f"\nProspect: {row.name}")
            print(f"  MLB Player ID: {row.mlb_player_id}")
            print(f"  FG Player ID: {row.fg_player_id}")
            print(f"  Position: {row.position}")
            print(f"  Current Level: {row.current_level}")
            print(f"  Pitches Collected: {row.batter_pitches}")
            print(f"  Games with Data: {row.batter_games}")
            print(f"  Levels Tracked: {row.batter_levels}")
            print(f"  Date Range: {row.first_batter_pitch} to {row.last_batter_pitch}")

            # Check their game logs to see what we should have
            game_log_query = text("""
                SELECT
                    level,
                    COUNT(*) as games,
                    MIN(game_date) as first_game,
                    MAX(game_date) as last_game,
                    SUM(pa) as total_pa
                FROM milb_batter_game_logs
                WHERE mlb_player_id::text = :player_id
                  AND game_date >= '2024-01-01'
                GROUP BY level
                ORDER BY level
            """)

            game_result = await db.execute(game_log_query, {"player_id": str(row.mlb_player_id)})
            game_rows = game_result.fetchall()

            print(f"\n  Game Logs (2024):")
            for game_row in game_rows:
                print(f"    {game_row.level}: {game_row.games} games, {game_row.total_pa} PA ({game_row.first_game} to {game_row.last_game})")


async def analyze_top_prospects_coverage():
    """Analyze pitch data coverage for top 100 prospects."""

    async with AsyncSessionLocal() as db:
        query = text("""
            WITH top_prospects AS (
                SELECT
                    p.id,
                    p.name,
                    p.mlb_player_id,
                    p.position,
                    p.current_level,
                    p.fg_player_id,
                    p.fangraphs_fv_latest,
                    ROW_NUMBER() OVER (ORDER BY p.fangraphs_fv_latest DESC NULLS LAST) as rank
                FROM prospects p
                WHERE p.fangraphs_fv_latest IS NOT NULL
                  AND p.mlb_player_id IS NOT NULL
            ),
            pitch_data_summary AS (
                SELECT
                    mlb_batter_id as mlb_player_id,
                    COUNT(DISTINCT pitch_id) as total_pitches,
                    COUNT(DISTINCT game_date) as games_with_pitches,
                    STRING_AGG(DISTINCT level::text, ', ' ORDER BY level::text) as levels,
                    MIN(game_date) as first_pitch,
                    MAX(game_date) as last_pitch
                FROM milb_batter_pitches
                WHERE game_date >= '2024-01-01'
                GROUP BY mlb_batter_id
            ),
            game_log_summary AS (
                SELECT
                    mlb_player_id,
                    COUNT(*) as total_games,
                    SUM(pa) as total_pa,
                    STRING_AGG(DISTINCT level::text, ', ' ORDER BY level::text) as game_levels,
                    MIN(game_date) as first_game,
                    MAX(game_date) as last_game
                FROM milb_batter_game_logs
                WHERE game_date >= '2024-01-01'
                GROUP BY mlb_player_id
            )
            SELECT
                tp.rank,
                tp.name,
                tp.position,
                tp.current_level,
                tp.fangraphs_fv_latest as fv,
                COALESCE(pds.total_pitches, 0) as pitches_collected,
                COALESCE(pds.games_with_pitches, 0) as games_with_pitch_data,
                COALESCE(gls.total_games, 0) as total_games_played,
                COALESCE(gls.total_pa, 0) as total_pa,
                pds.levels as pitch_levels,
                gls.game_levels,
                CASE
                    WHEN pds.total_pitches > 0 AND gls.total_pa > 0
                    THEN ROUND((pds.total_pitches::numeric / gls.total_pa) * 100, 1)
                    ELSE 0
                END as coverage_pct
            FROM top_prospects tp
            LEFT JOIN pitch_data_summary pds ON tp.mlb_player_id = pds.mlb_player_id
            LEFT JOIN game_log_summary gls ON tp.mlb_player_id = gls.mlb_player_id
            WHERE tp.rank <= 100
              AND tp.position NOT IN ('SP', 'RP', 'P')  -- Hitters only
            ORDER BY
                CASE WHEN pds.total_pitches = 0 THEN 0 ELSE 1 END,  -- No data first
                coverage_pct,  -- Then by coverage
                tp.rank
            LIMIT 50
        """)

        result = await db.execute(query)
        rows = result.fetchall()

        print("\n" + "="*120)
        print("TOP PROSPECTS PITCH DATA COVERAGE ANALYSIS (Bottom 50 by coverage)")
        print("="*120)
        print(f"{'Rank':<6} {'Name':<25} {'Pos':<5} {'FV':<5} {'Pitches':<10} {'Games':<8} {'PA':<6} {'Coverage':<10} {'Pitch Levels':<20} {'Game Levels':<20}")
        print("-"*120)

        no_data_count = 0
        partial_data_count = 0

        for row in rows:
            coverage_str = f"{row.coverage_pct}%" if row.coverage_pct > 0 else "NO DATA"

            if row.pitches_collected == 0:
                no_data_count += 1
                coverage_indicator = "❌"
            elif row.coverage_pct < 50:
                partial_data_count += 1
                coverage_indicator = "⚠️ "
            else:
                coverage_indicator = "✓ "

            print(f"{coverage_indicator} {row.rank:<4} {row.name:<25} {row.position:<5} {row.fv:<5} {row.pitches_collected:<10} {row.games_with_pitch_data:<8} {row.total_pa:<6} {coverage_str:<10} {(row.pitch_levels or 'N/A'):<20} {(row.game_levels or 'N/A'):<20}")

        print("\n" + "="*120)
        print(f"Summary:")
        print(f"  Prospects with NO pitch data: {no_data_count}")
        print(f"  Prospects with <50% coverage: {partial_data_count}")
        print(f"  Total needing attention: {no_data_count + partial_data_count}")


async def identify_level_gaps():
    """Identify which levels have missing data."""

    async with AsyncSessionLocal() as db:
        query = text("""
            WITH game_log_levels AS (
                SELECT DISTINCT
                    p.mlb_player_id,
                    p.name,
                    gl.level
                FROM prospects p
                JOIN milb_batter_game_logs gl ON p.mlb_player_id = gl.mlb_player_id
                WHERE gl.game_date >= '2024-01-01'
                  AND p.fangraphs_fv_latest > 45
            ),
            pitch_data_levels AS (
                SELECT DISTINCT
                    mlb_batter_id as mlb_player_id,
                    level
                FROM milb_batter_pitches
                WHERE game_date >= '2024-01-01'
            )
            SELECT
                gll.level,
                COUNT(DISTINCT gll.mlb_player_id) as prospects_at_level,
                COUNT(DISTINCT pdl.mlb_player_id) as prospects_with_pitch_data,
                COUNT(DISTINCT gll.mlb_player_id) - COUNT(DISTINCT pdl.mlb_player_id) as missing_pitch_data
            FROM game_log_levels gll
            LEFT JOIN pitch_data_levels pdl ON gll.mlb_player_id = pdl.mlb_player_id
                AND gll.level = pdl.level
            GROUP BY gll.level
            ORDER BY missing_pitch_data DESC
        """)

        result = await db.execute(query)
        rows = result.fetchall()

        print("\n" + "="*80)
        print("PITCH DATA COVERAGE BY LEVEL")
        print("="*80)
        print(f"{'Level':<10} {'Prospects':<15} {'With Data':<15} {'Missing':<15} {'Coverage %':<15}")
        print("-"*80)

        for row in rows:
            coverage_pct = (row.prospects_with_pitch_data / row.prospects_at_level * 100) if row.prospects_at_level > 0 else 0
            print(f"{row.level:<10} {row.prospects_at_level:<15} {row.prospects_with_pitch_data:<15} {row.missing_pitch_data:<15} {coverage_pct:.1f}%")


async def find_prospects_missing_all_pitch_data():
    """Find top 100 prospects with zero pitch data."""

    async with AsyncSessionLocal() as db:
        query = text("""
            WITH top_prospects AS (
                SELECT
                    p.id,
                    p.name,
                    p.mlb_player_id,
                    p.position,
                    p.current_level,
                    p.fangraphs_fv_latest,
                    ROW_NUMBER() OVER (ORDER BY p.fangraphs_fv_latest DESC NULLS LAST) as rank
                FROM prospects p
                WHERE p.fangraphs_fv_latest IS NOT NULL
                  AND p.mlb_player_id IS NOT NULL
            ),
            pitch_counts AS (
                SELECT
                    mlb_batter_id as mlb_player_id,
                    COUNT(*) as pitch_count
                FROM milb_batter_pitches
                WHERE game_date >= '2024-01-01'
                GROUP BY mlb_batter_id
            ),
            game_counts AS (
                SELECT
                    mlb_player_id,
                    COUNT(*) as games,
                    SUM(pa) as total_pa,
                    STRING_AGG(DISTINCT level::text, ', ' ORDER BY level::text) as levels
                FROM milb_batter_game_logs
                WHERE game_date >= '2024-01-01'
                GROUP BY mlb_player_id
            )
            SELECT
                tp.rank,
                tp.name,
                tp.mlb_player_id,
                tp.position,
                tp.current_level,
                tp.fangraphs_fv_latest as fv,
                gc.games,
                gc.total_pa,
                gc.levels
            FROM top_prospects tp
            LEFT JOIN pitch_counts pc ON tp.mlb_player_id = pc.mlb_player_id
            LEFT JOIN game_counts gc ON tp.mlb_player_id = gc.mlb_player_id
            WHERE tp.rank <= 100
              AND tp.position NOT IN ('SP', 'RP', 'P')
              AND pc.pitch_count IS NULL
              AND gc.total_pa > 0  -- They played, but we have no pitch data
            ORDER BY tp.rank
        """)

        result = await db.execute(query)
        rows = result.fetchall()

        print("\n" + "="*100)
        print("TOP 100 HITTERS WITH ZERO PITCH DATA (but they played games)")
        print("="*100)
        print(f"{'Rank':<6} {'Name':<25} {'MLB ID':<12} {'Pos':<5} {'Level':<8} {'FV':<5} {'Games':<8} {'PA':<6} {'Levels Played'}")
        print("-"*100)

        for row in rows:
            print(f"{row.rank:<6} {row.name:<25} {row.mlb_player_id:<12} {row.position:<5} {row.current_level or 'N/A':<8} {row.fv:<5} {row.games:<8} {row.total_pa:<6} {row.levels}")

        print(f"\nTotal: {len(rows)} prospects with zero pitch data")


async def main():
    """Run all investigations."""
    print("\n" + "="*80)
    print("MILB PITCH-BY-PITCH DATA GAP ANALYSIS")
    print("="*80)

    await investigate_specific_prospects()
    await find_prospects_missing_all_pitch_data()
    await analyze_top_prospects_coverage()
    await identify_level_gaps()

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
