"""
Analyze MiLB Data Coverage Gaps (2021-2023)
============================================

This script identifies:
1. How much MiLB data we have for 2021-2023
2. Which prospects have MLB data but are missing MiLB data
3. Specific players we should collect MiLB data for

Goal: Expand training dataset from 20 → 100+ samples

Usage:
    python scripts/analyze_milb_data_gaps.py
"""

import asyncio
import asyncpg
from datetime import datetime
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def analyze_coverage():
    """Analyze MiLB data coverage for 2021-2023."""

    print("="*80)
    print("MiLB DATA COVERAGE ANALYSIS (2021-2023)")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 1. Current MiLB data coverage by season
        print("\n" + "="*80)
        print("1. CURRENT MiLB GAME LOGS COVERAGE")
        print("="*80)

        query = """
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                COUNT(*) as total_games,
                SUM(CASE WHEN plate_appearances > 0 THEN 1 ELSE 0 END) as hitter_games,
                SUM(CASE WHEN games_pitched > 0 THEN 1 ELSE 0 END) as pitcher_games
            FROM milb_game_logs
            WHERE season BETWEEN 2021 AND 2023
            GROUP BY season
            ORDER BY season
        """

        rows = await conn.fetch(query)

        print("\n| Season | Unique Players | Total Games | Hitter Games | Pitcher Games |")
        print("|--------|----------------|-------------|--------------|---------------|")
        for row in rows:
            print(f"| {row['season']} | {row['unique_players']:>14} | {row['total_games']:>11} | {row['hitter_games']:>12} | {row['pitcher_games']:>13} |")

        if not rows:
            print("\n⚠️  NO MiLB DATA FOUND FOR 2021-2023!")
            print("    We need to collect MiLB game logs for these seasons.\n")

        # 2. Prospects with MLB data but NO MiLB data
        print("\n" + "="*80)
        print("2. PROSPECTS WITH MLB DATA BUT MISSING MiLB DATA (2021-2023)")
        print("="*80)

        query = """
            WITH mlb_prospects AS (
                SELECT DISTINCT
                    p.id,
                    p.mlb_player_id::integer as mlb_player_id,
                    p.name,
                    p.position,
                    MIN(mlb.season) as mlb_debut_season,
                    COUNT(DISTINCT mlb.id) as mlb_games
                FROM prospects p
                INNER JOIN mlb_game_logs mlb
                    ON p.mlb_player_id::integer = mlb.mlb_player_id
                WHERE p.mlb_player_id IS NOT NULL
                    AND p.mlb_player_id ~ '^[0-9]+$'
                    AND mlb.season >= 2021  -- Debuted 2021 or later
                GROUP BY p.id, p.mlb_player_id, p.name, p.position
                HAVING COUNT(DISTINCT mlb.id) >= 20  -- Minimum 20 MLB games
            ),
            milb_coverage AS (
                SELECT DISTINCT
                    p.mlb_player_id::integer as mlb_player_id,
                    COUNT(DISTINCT milb.id) as milb_games,
                    MIN(milb.season) as first_milb_season,
                    MAX(milb.season) as last_milb_season
                FROM prospects p
                INNER JOIN milb_game_logs milb
                    ON p.mlb_player_id::integer = milb.mlb_player_id
                WHERE p.mlb_player_id IS NOT NULL
                    AND p.mlb_player_id ~ '^[0-9]+$'
                    AND milb.season BETWEEN 2021 AND 2023
                GROUP BY p.mlb_player_id
            )
            SELECT
                mlb.id,
                mlb.mlb_player_id,
                mlb.name,
                mlb.position,
                mlb.mlb_debut_season,
                mlb.mlb_games,
                COALESCE(milb.milb_games, 0) as milb_games,
                milb.first_milb_season,
                milb.last_milb_season
            FROM mlb_prospects mlb
            LEFT JOIN milb_coverage milb
                ON mlb.mlb_player_id = milb.mlb_player_id
            ORDER BY
                CASE WHEN milb.milb_games IS NULL THEN 0 ELSE 1 END,  -- NULL first
                milb.milb_games ASC,
                mlb.mlb_games DESC
        """

        rows = await conn.fetch(query)

        missing_milb = [r for r in rows if r['milb_games'] == 0]
        partial_milb = [r for r in rows if r['milb_games'] > 0]

        print(f"\n📊 Total prospects with MLB data (2021+, 20+ games): {len(rows)}")
        print(f"   ❌ Missing MiLB data (2021-2023): {len(missing_milb)}")
        print(f"   ✅ Have MiLB data (2021-2023): {len(partial_milb)}")

        if missing_milb:
            print(f"\n🎯 TOP 20 PROSPECTS MISSING MiLB DATA (High Priority):")
            print("\n| ID | MLB Player ID | Name | Position | MLB Debut | MLB Games |")
            print("|-----|---------------|------|----------|-----------|-----------|")
            for row in missing_milb[:20]:
                print(f"| {row['id']} | {row['mlb_player_id']} | {row['name']} | {row['position']} | {row['mlb_debut_season']} | {row['mlb_games']} |")

        # 3. Breakdown by position
        print("\n" + "="*80)
        print("3. MISSING DATA BREAKDOWN BY POSITION")
        print("="*80)

        hitters_missing = [r for r in missing_milb if r['position'] not in ['SP', 'RP', 'LHP', 'RHP']]
        pitchers_missing = [r for r in missing_milb if r['position'] in ['SP', 'RP', 'LHP', 'RHP']]

        print(f"\nHitters missing MiLB data: {len(hitters_missing)}")
        print(f"Pitchers missing MiLB data: {len(pitchers_missing)}")

        # 4. Estimate potential training samples
        print("\n" + "="*80)
        print("4. POTENTIAL TRAINING DATASET SIZE")
        print("="*80)

        print(f"\nCurrent training samples: 20")
        print(f"Prospects with MLB data but missing MiLB: {len(missing_milb)}")
        print(f"Prospects with partial MiLB data: {len(partial_milb)}")
        print(f"\n🎯 POTENTIAL after collecting MiLB data: {len(rows)} training samples")
        print(f"   Expected increase: {len(rows) - 20} → +{((len(rows) - 20) / 20 * 100):.0f}% improvement!")

        # 5. Recommendations
        print("\n" + "="*80)
        print("5. RECOMMENDATIONS")
        print("="*80)

        print("""
📋 Action Items:

1. **Collect MiLB Game Logs for 2021-2023**
   - Focus on prospects who have MLB data
   - Priority: Top prospects with most MLB games
   - Use existing collection scripts or MLB Stats API

2. **Specific Players to Collect:**""")

        if missing_milb:
            print(f"   - {len(missing_milb)} prospects with NO MiLB data")
            print("\n   Top 5 priorities (most MLB games):")
            for i, row in enumerate(missing_milb[:5], 1):
                print(f"   {i}. {row['name']} ({row['position']}) - {row['mlb_games']} MLB games")

        print("""
3. **Collection Strategy:**
   - Use MLB Stats API gameLog endpoint
   - Filter by sport_id for MiLB levels (11=AAA, 12=AA, etc.)
   - Seasons: 2021, 2022, 2023
   - Store in milb_game_logs table

4. **Expected Impact:**
   - Training dataset: 20 → {total} samples (+{increase}%)
   - Better model reliability with more data
   - Include both hitters AND pitchers
        """.format(total=len(rows), increase=((len(rows) - 20) / 20 * 100)))

        # 6. Generate collection list
        print("\n" + "="*80)
        print("6. GENERATING COLLECTION LIST")
        print("="*80)

        if missing_milb:
            filename = f"milb_collection_priority_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            with open(filename, 'w') as f:
                f.write("prospect_id,mlb_player_id,name,position,mlb_debut_season,mlb_games,priority\n")
                for i, row in enumerate(missing_milb, 1):
                    f.write(f"{row['id']},{row['mlb_player_id']},{row['name']},{row['position']},{row['mlb_debut_season']},{row['mlb_games']},high\n")
                for i, row in enumerate(partial_milb, 1):
                    f.write(f"{row['id']},{row['mlb_player_id']},{row['name']},{row['position']},{row['mlb_debut_season']},{row['mlb_games']},medium\n")

            print(f"\n✅ Saved collection list: {filename}")
            print(f"   Total prospects to collect: {len(missing_milb) + len(partial_milb)}")

    finally:
        await conn.close()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(analyze_coverage())
