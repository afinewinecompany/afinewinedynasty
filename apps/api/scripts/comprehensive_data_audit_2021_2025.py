"""
Comprehensive Data Audit: 2021-2025 MLB & MiLB Coverage
=========================================================

Identify blindspots and gaps in our data collection.

Goal: Find ALL prospects who should be in training data but aren't.

Usage:
    python scripts/comprehensive_data_audit_2021_2025.py
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


async def audit():
    """Comprehensive data audit."""

    print("="*80)
    print("COMPREHENSIVE DATA AUDIT: 2021-2025")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # ============================================
        # 1. MLB GAME LOGS COVERAGE
        # ============================================
        print("\n" + "="*80)
        print("1. MLB GAME LOGS - UNIQUE PLAYERS BY SEASON")
        print("="*80)

        query = """
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                COUNT(*) as total_games,
                SUM(CASE WHEN plate_appearances > 0 THEN 1 ELSE 0 END) as hitter_games
            FROM mlb_game_logs
            WHERE season BETWEEN 2021 AND 2025
            GROUP BY season
            ORDER BY season
        """

        rows = await conn.fetch(query)

        print("\n| Season | Unique Players | Total Games | Hitter Games |")
        print("|--------|----------------|-------------|--------------|")
        for row in rows:
            print(f"| {row['season']} | {row['unique_players']:>14} | {row['total_games']:>11} | {row['hitter_games']:>12} |")

        total_mlb_players = await conn.fetchval("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM mlb_game_logs
            WHERE season BETWEEN 2021 AND 2025
        """)

        print(f"\nTotal unique MLB players (2021-2025): {total_mlb_players}")

        # ============================================
        # 2. MiLB GAME LOGS COVERAGE
        # ============================================
        print("\n" + "="*80)
        print("2. MiLB GAME LOGS - UNIQUE PLAYERS BY SEASON")
        print("="*80)

        query = """
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as unique_players,
                COUNT(*) as total_games,
                SUM(CASE WHEN plate_appearances > 0 THEN 1 ELSE 0 END) as hitter_games,
                SUM(CASE WHEN games_pitched > 0 THEN 1 ELSE 0 END) as pitcher_games
            FROM milb_game_logs
            WHERE season BETWEEN 2021 AND 2025
            GROUP BY season
            ORDER BY season
        """

        rows = await conn.fetch(query)

        print("\n| Season | Unique Players | Total Games | Hitter Games | Pitcher Games |")
        print("|--------|----------------|-------------|--------------|---------------|")
        for row in rows:
            print(f"| {row['season']} | {row['unique_players']:>14} | {row['total_games']:>11} | {row['hitter_games']:>12} | {row['pitcher_games']:>13} |")

        total_milb_players = await conn.fetchval("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM milb_game_logs
            WHERE season BETWEEN 2021 AND 2025
        """)

        print(f"\nTotal unique MiLB players (2021-2025): {total_milb_players}")

        # ============================================
        # 3. PROSPECTS TABLE COVERAGE
        # ============================================
        print("\n" + "="*80)
        print("3. PROSPECTS TABLE - MLB_PLAYER_ID COVERAGE")
        print("="*80)

        total_prospects = await conn.fetchval("SELECT COUNT(*) FROM prospects")
        prospects_with_mlb_id = await conn.fetchval("""
            SELECT COUNT(*)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            AND mlb_player_id ~ '^[0-9]+$'
        """)

        print(f"\nTotal prospects in table: {total_prospects}")
        print(f"Prospects with valid MLB Player ID: {prospects_with_mlb_id}")
        print(f"Missing MLB Player ID: {total_prospects - prospects_with_mlb_id} ({(total_prospects - prospects_with_mlb_id) / total_prospects * 100:.1f}%)")

        # ============================================
        # 4. CROSS-REFERENCE: PROSPECTS vs MLB GAME LOGS
        # ============================================
        print("\n" + "="*80)
        print("4. CROSS-REFERENCE: PROSPECTS TABLE vs MLB GAME LOGS")
        print("="*80)

        # Prospects in table but NOT in MLB game logs
        query = """
            SELECT COUNT(*) as count
            FROM prospects p
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id ~ '^[0-9]+$'
            AND NOT EXISTS (
                SELECT 1
                FROM mlb_game_logs mlb
                WHERE mlb.mlb_player_id = p.mlb_player_id::integer
            )
        """

        prospects_missing_mlb_data = await conn.fetchval(query)

        # MLB players NOT in prospects table
        query = """
            SELECT COUNT(DISTINCT mlb_player_id) as count
            FROM mlb_game_logs
            WHERE season BETWEEN 2021 AND 2025
            AND NOT EXISTS (
                SELECT 1
                FROM prospects p
                WHERE p.mlb_player_id::integer = mlb_game_logs.mlb_player_id
            )
        """

        mlb_players_not_in_prospects = await conn.fetchval(query)

        print(f"\nProspects in table but NOT in MLB game logs: {prospects_missing_mlb_data}")
        print(f"MLB players (2021-2025) NOT in prospects table: {mlb_players_not_in_prospects}")

        # ============================================
        # 5. CROSS-REFERENCE: PROSPECTS vs MiLB GAME LOGS
        # ============================================
        print("\n" + "="*80)
        print("5. CROSS-REFERENCE: PROSPECTS TABLE vs MiLB GAME LOGS")
        print("="*80)

        # Prospects in table but NOT in MiLB game logs
        query = """
            SELECT COUNT(*) as count
            FROM prospects p
            WHERE p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id ~ '^[0-9]+$'
            AND NOT EXISTS (
                SELECT 1
                FROM milb_game_logs milb
                WHERE milb.mlb_player_id = p.mlb_player_id::integer
            )
        """

        prospects_missing_milb_data = await conn.fetchval(query)

        # MiLB players NOT in prospects table
        query = """
            SELECT COUNT(DISTINCT mlb_player_id) as count
            FROM milb_game_logs
            WHERE season BETWEEN 2021 AND 2025
            AND NOT EXISTS (
                SELECT 1
                FROM prospects p
                WHERE p.mlb_player_id::integer = milb_game_logs.mlb_player_id
            )
        """

        milb_players_not_in_prospects = await conn.fetchval(query)

        print(f"\nProspects in table but NOT in MiLB game logs: {prospects_missing_milb_data}")
        print(f"MiLB players (2021-2025) NOT in prospects table: {milb_players_not_in_prospects}")

        # ============================================
        # 6. THE MONEY QUESTION: MLB DEBUTS 2021-2025
        # ============================================
        print("\n" + "="*80)
        print("6. MLB DEBUTS 2021-2025 - HOW MANY SHOULD WE HAVE?")
        print("="*80)

        # Players who debuted in MLB 2021-2025 (first MLB game in this period)
        query = """
            WITH first_mlb_game AS (
                SELECT
                    mlb_player_id,
                    MIN(season) as debut_season,
                    COUNT(*) as career_mlb_games
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            )
            SELECT
                debut_season,
                COUNT(*) as debuts,
                SUM(CASE WHEN career_mlb_games >= 20 THEN 1 ELSE 0 END) as debuts_20plus_games
            FROM first_mlb_game
            WHERE debut_season BETWEEN 2021 AND 2025
            GROUP BY debut_season
            ORDER BY debut_season
        """

        rows = await conn.fetch(query)

        print("\n| Debut Season | Total Debuts | Debuts w/ 20+ Games |")
        print("|--------------|--------------|---------------------|")
        total_debuts = 0
        total_debuts_20plus = 0
        for row in rows:
            print(f"| {row['debut_season']} | {row['debuts']:>12} | {row['debuts_20plus_games']:>19} |")
            total_debuts += row['debuts']
            total_debuts_20plus += row['debuts_20plus_games']

        print(f"\nTOTAL MLB DEBUTS (2021-2025): {total_debuts}")
        print(f"TOTAL w/ 20+ games: {total_debuts_20plus}")

        # ============================================
        # 7. THE BLINDSPOT: WHO ARE WE MISSING?
        # ============================================
        print("\n" + "="*80)
        print("7. IDENTIFYING BLINDSPOTS - MLB PLAYERS NOT IN PROSPECTS TABLE")
        print("="*80)

        query = """
            WITH mlb_debuts_2021_2025 AS (
                SELECT
                    mlb_player_id,
                    MIN(season) as debut_season,
                    COUNT(*) as mlb_games
                FROM mlb_game_logs
                WHERE season BETWEEN 2021 AND 2025
                GROUP BY mlb_player_id
                HAVING COUNT(*) >= 20  -- At least 20 games
            )
            SELECT
                mlb.mlb_player_id,
                mlb.debut_season,
                mlb.mlb_games,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM prospects p
                        WHERE p.mlb_player_id::integer = mlb.mlb_player_id
                    ) THEN 'In Prospects Table'
                    ELSE 'MISSING FROM PROSPECTS'
                END as status
            FROM mlb_debuts_2021_2025 mlb
            ORDER BY mlb.mlb_games DESC
        """

        rows = await conn.fetch(query)

        missing_from_prospects = [r for r in rows if r['status'] == 'MISSING FROM PROSPECTS']
        in_prospects = [r for r in rows if r['status'] == 'In Prospects Table']

        print(f"\nMLB players (2021-2025, 20+ games): {len(rows)}")
        print(f"  ✅ In prospects table: {len(in_prospects)}")
        print(f"  ❌ MISSING from prospects table: {len(missing_from_prospects)}")

        if missing_from_prospects:
            print(f"\nTop 20 MLB players NOT in prospects table:")
            print("\n| MLB Player ID | Debut Season | MLB Games | Status |")
            print("|---------------|--------------|-----------|--------|")
            for r in missing_from_prospects[:20]:
                print(f"| {r['mlb_player_id']} | {r['debut_season']} | {r['mlb_games']:>9} | MISSING |")

        # ============================================
        # 8. THE OTHER BLINDSPOT: PROSPECTS WITH MLB DATA BUT NO MiLB DATA
        # ============================================
        print("\n" + "="*80)
        print("8. PROSPECTS WITH MLB DATA BUT MISSING MiLB DATA (2021-2025)")
        print("="*80)

        query = """
            WITH prospects_with_mlb AS (
                SELECT
                    p.id,
                    p.mlb_player_id::integer as mlb_player_id,
                    p.name,
                    p.position,
                    MIN(mlb.season) as mlb_debut,
                    COUNT(DISTINCT mlb.id) as mlb_games
                FROM prospects p
                INNER JOIN mlb_game_logs mlb
                    ON p.mlb_player_id::integer = mlb.mlb_player_id
                WHERE p.mlb_player_id IS NOT NULL
                    AND p.mlb_player_id ~ '^[0-9]+$'
                    AND mlb.season BETWEEN 2021 AND 2025
                GROUP BY p.id, p.mlb_player_id, p.name, p.position
                HAVING COUNT(DISTINCT mlb.id) >= 20
            )
            SELECT
                p.id,
                p.mlb_player_id,
                p.name,
                p.position,
                p.mlb_debut,
                p.mlb_games,
                COUNT(DISTINCT milb.id) as milb_games
            FROM prospects_with_mlb p
            LEFT JOIN milb_game_logs milb
                ON p.mlb_player_id = milb.mlb_player_id
                AND milb.season BETWEEN 2018 AND 2025  -- Look back further
            GROUP BY p.id, p.mlb_player_id, p.name, p.position, p.mlb_debut, p.mlb_games
            ORDER BY
                CASE WHEN COUNT(DISTINCT milb.id) = 0 THEN 0 ELSE 1 END,
                COUNT(DISTINCT milb.id) ASC,
                p.mlb_games DESC
        """

        rows = await conn.fetch(query)

        no_milb = [r for r in rows if r['milb_games'] == 0]
        has_milb = [r for r in rows if r['milb_games'] > 0]

        print(f"\nProspects with MLB games (2021-2025, 20+ games): {len(rows)}")
        print(f"  ✅ Have MiLB data: {len(has_milb)}")
        print(f"  ❌ MISSING MiLB data: {len(no_milb)}")

        if no_milb:
            print(f"\nProspects with MLB data but NO MiLB data:")
            print("\n| ID | MLB Player ID | Name | Position | MLB Debut | MLB Games |")
            print("|----|---------------|------|----------|-----------|-----------|")
            for r in no_milb[:20]:
                print(f"| {r['id']} | {r['mlb_player_id']} | {r['name']} | {r['position']} | {r['mlb_debut']} | {r['mlb_games']} |")

        # ============================================
        # 9. SUMMARY & RECOMMENDATIONS
        # ============================================
        print("\n" + "="*80)
        print("9. SUMMARY & RECOMMENDATIONS")
        print("="*80)

        print(f"""
CURRENT STATE:
- MLB players in database (2021-2025): {total_mlb_players:,}
- MiLB players in database (2021-2025): {total_milb_players:,}
- MLB debuts 2021-2025 (20+ games): {total_debuts_20plus:,}
- Prospects in our table: {total_prospects:,}

BLINDSPOTS IDENTIFIED:
1. MLB players NOT in prospects table: {len(missing_from_prospects)} players
2. Prospects with MLB but NO MiLB data: {len(no_milb)} prospects

CURRENT TRAINING DATA:
- Expected samples (prospects with both MLB + MiLB): {len(has_milb)}
- Actually extracted: 22
- Missing: {len(has_milb) - 22}

ACTION ITEMS:
1. ADD MISSING MLB PLAYERS TO PROSPECTS TABLE
   - {len(missing_from_prospects)} MLB players (2021-2025) not in prospects table
   - These are likely international FAs, undrafted FAs, or older prospects
   - Need to create prospect records for them

2. COLLECT MISSING MiLB DATA
   - {len(no_milb)} prospects have MLB games but NO MiLB data
   - Need to run MiLB collection for these players (2018-2023)

3. INVESTIGATE WHY ONLY 22/37 EXTRACTED
   - We have 37 prospects with both MLB and MiLB data
   - Training data builder only successfully extracted 22
   - Likely: Missing stats, insufficient MLB games, or data quality issues
        """)

        # Save detailed lists
        print("\n" + "="*80)
        print("10. SAVING DETAILED LISTS")
        print("="*80)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # List 1: MLB players missing from prospects
        if missing_from_prospects:
            filename = f"mlb_players_missing_from_prospects_{timestamp}.csv"
            with open(filename, 'w') as f:
                f.write("mlb_player_id,debut_season,mlb_games\n")
                for r in missing_from_prospects:
                    f.write(f"{r['mlb_player_id']},{r['debut_season']},{r['mlb_games']}\n")
            print(f"\n✅ Saved: {filename} ({len(missing_from_prospects)} players)")

        # List 2: Prospects with MLB but no MiLB
        if no_milb:
            filename = f"prospects_missing_milb_data_{timestamp}.csv"
            with open(filename, 'w') as f:
                f.write("prospect_id,mlb_player_id,name,position,mlb_debut,mlb_games\n")
                for r in no_milb:
                    f.write(f"{r['id']},{r['mlb_player_id']},{r['name']},{r['position']},{r['mlb_debut']},{r['mlb_games']}\n")
            print(f"✅ Saved: {filename} ({len(no_milb)} prospects)")

    finally:
        await conn.close()

    print("\n" + "="*80)
    print("AUDIT COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(audit())
