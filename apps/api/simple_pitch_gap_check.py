"""
Simple check of pitch data gaps for specific prospects.
"""

import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal


async def check_specific_prospects():
    """Check Konnor Griffin and Bryce Eldridge specifically."""

    async with AsyncSessionLocal() as db:
        # Get prospect info
        prospects = await db.execute(text("""
            SELECT name, mlb_player_id, position, current_level
            FROM prospects
            WHERE name IN ('Konnor Griffin', 'Bryce Eldridge')
            ORDER BY name
        """))

        for prospect in prospects:
            print(f"\n{'='*80}")
            print(f"Prospect: {prospect.name}")
            print(f"MLB ID: {prospect.mlb_player_id}")
            print(f"Position: {prospect.position}")
            print(f"Current Level: {prospect.current_level}")

            # Check pitch data (convert to int as mlb_batter_id is integer)
            pitch_data = await db.execute(text("""
                SELECT
                    COUNT(*) as total_pitches,
                    COUNT(DISTINCT game_date) as games,
                    MIN(game_date) as first_date,
                    MAX(game_date) as last_date,
                    STRING_AGG(DISTINCT level, ', ' ORDER BY level) as levels
                FROM milb_batter_pitches
                WHERE mlb_batter_id = :player_id
                  AND game_date >= '2024-01-01'
            """), {"player_id": int(prospect.mlb_player_id)})

            pitch_row = pitch_data.first()
            print(f"\nPitch Data (2024):")
            print(f"  Total Pitches: {pitch_row.total_pitches}")
            print(f"  Games: {pitch_row.games}")
            print(f"  Date Range: {pitch_row.first_date} to {pitch_row.last_date}")
            print(f"  Levels: {pitch_row.levels or 'None'}")

            # Check game logs
            game_data = await db.execute(text("""
                SELECT
                    level,
                    COUNT(*) as games,
                    SUM(pa) as total_pa,
                    MIN(game_date) as first_date,
                    MAX(game_date) as last_date
                FROM milb_batter_game_logs
                WHERE mlb_player_id = :player_id
                  AND game_date >= '2024-01-01'
                GROUP BY level
                ORDER BY level
            """), {"player_id": prospect.mlb_player_id})

            print(f"\nGame Logs (2024) by Level:")
            for game_row in game_data:
                print(f"  {game_row.level}: {game_row.games} games, {game_row.total_pa} PA ({game_row.first_date} to {game_row.last_date})")

                # Check pitch data for this specific level
                level_pitch = await db.execute(text("""
                    SELECT COUNT(*) as pitches
                    FROM milb_batter_pitches
                    WHERE mlb_batter_id = :player_id
                      AND level = :level
                      AND game_date >= '2024-01-01'
                """), {"player_id": int(prospect.mlb_player_id), "level": game_row.level})

                level_row = level_pitch.first()
                coverage = (level_row.pitches / game_row.total_pa * 100) if game_row.total_pa > 0 else 0
                print(f"    -> Pitch data: {level_row.pitches} pitches ({coverage:.1f}% of PA)")


async def check_top_prospects_no_data():
    """Find top 100 prospects with NO pitch data at all."""

    async with AsyncSessionLocal() as db:
        query = text("""
            WITH top_hitters AS (
                SELECT
                    name,
                    mlb_player_id,
                    position,
                    current_level,
                    fangraphs_fv_latest as fv,
                    ROW_NUMBER() OVER (ORDER BY fangraphs_fv_latest DESC NULLS LAST) as rank
                FROM prospects
                WHERE fangraphs_fv_latest IS NOT NULL
                  AND mlb_player_id IS NOT NULL
                  AND position NOT IN ('SP', 'RP', 'P')
            )
            SELECT
                th.rank,
                th.name,
                th.mlb_player_id,
                th.position,
                th.current_level,
                th.fv,
                COALESCE(COUNT(DISTINCT bp.pitch_id), 0) as pitch_count,
                COALESCE(SUM(gl.pa), 0) as total_pa
            FROM top_hitters th
            LEFT JOIN milb_batter_pitches bp ON th.mlb_player_id = bp.mlb_batter_id
                AND bp.game_date >= '2024-01-01'
            LEFT JOIN milb_batter_game_logs gl ON th.mlb_player_id = gl.mlb_player_id
                AND gl.game_date >= '2024-01-01'
            WHERE th.rank <= 100
            GROUP BY th.rank, th.name, th.mlb_player_id, th.position, th.current_level, th.fv
            HAVING COALESCE(COUNT(DISTINCT bp.pitch_id), 0) = 0
               AND COALESCE(SUM(gl.pa), 0) > 0
            ORDER BY th.rank
        """)

        result = await db.execute(query)
        rows = result.fetchall()

        print(f"\n{'='*100}")
        print(f"TOP 100 HITTERS WITH ZERO PITCH DATA (but they have game logs)")
        print(f"{'='*100}")
        print(f"{'Rank':<6} {'Name':<25} {'ID':<10} {'Pos':<5} {'Level':<8} {'FV':<5} {'PA':<6}")
        print(f"{'-'*100}")

        for row in rows:
            print(f"{row.rank:<6} {row.name:<25} {row.mlb_player_id:<10} {row.position:<5} {(row.current_level or 'N/A'):<8} {row.fv:<5.0f} {row.total_pa:<6}")

        print(f"\nTotal: {len(rows)} prospects")


async def main():
    print("PITCH DATA GAP INVESTIGATION\n")
    await check_specific_prospects()
    await check_top_prospects_no_data()


if __name__ == "__main__":
    asyncio.run(main())
