#!/usr/bin/env python3
"""
Check the scope of MiLB data - do we have ALL players or just our prospects?
This is critical for context-adjusted features like age-relative-to-level.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_data_scope():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
    conn = await asyncpg.connect(DATABASE_URL)

    print("="*80)
    print("DATA SCOPE ANALYSIS - Do we have ALL MiLB data or just our prospects?")
    print("="*80)

    # 1. Check how many unique players in game logs vs prospects
    print("\n[1] PLAYER COUNT COMPARISON")
    print("-" * 80)

    prospect_count = await conn.fetchval("SELECT COUNT(DISTINCT mlb_player_id) FROM prospects WHERE mlb_player_id IS NOT NULL")
    game_log_players = await conn.fetchval("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_game_logs")

    print(f"Prospects with MLB Player ID: {prospect_count:,}")
    print(f"Unique players in game logs: {game_log_players:,}")
    print(f"Ratio: {game_log_players / prospect_count:.1f}x more players in game logs")

    if game_log_players > prospect_count * 2:
        print("\n[OK] CONCLUSION: We have COMPREHENSIVE MiLB data, not just our prospects!")
        print("    This means we CAN calculate league-wide age-relative-to-level adjustments!")
    else:
        print("\n[WARN] CONCLUSION: We may only have prospect-specific data")
        print("       This limits our ability to calculate league-wide baselines")

    # 2. Check overlap - how many prospects are in game logs?
    print("\n\n[2] PROSPECT COVERAGE IN GAME LOGS")
    print("-" * 80)

    overlap = await conn.fetchrow("""
        SELECT
            COUNT(DISTINCT p.mlb_player_id) as prospects_with_player_id,
            COUNT(DISTINCT gl.mlb_player_id) as prospects_in_game_logs,
            COUNT(DISTINCT CASE WHEN gl.mlb_player_id IS NOT NULL THEN p.mlb_player_id END) as overlap
        FROM prospects p
        LEFT JOIN (SELECT DISTINCT mlb_player_id FROM milb_game_logs) gl
            ON p.mlb_player_id = gl.mlb_player_id
        WHERE p.mlb_player_id IS NOT NULL
    """)

    print(f"Prospects with player IDs: {overlap['prospects_with_player_id']:,}")
    print(f"Prospects found in game logs: {overlap['overlap']:,}")
    print(f"Coverage rate: {overlap['overlap'] / overlap['prospects_with_player_id'] * 100:.1f}%")

    missing = overlap['prospects_with_player_id'] - overlap['overlap']
    if missing > 0:
        print(f"\n[WARN] {missing} prospects NOT found in game logs")
        print("       (These may be very young prospects without MiLB experience yet)")

    # 3. Sample non-prospect players to see if we have league-wide data
    print("\n\n[3] SAMPLE NON-PROSPECT PLAYERS")
    print("-" * 80)

    non_prospects = await conn.fetch("""
        SELECT
            gl.mlb_player_id,
            COUNT(*) as game_count,
            MIN(gl.season) as first_season,
            MAX(gl.season) as last_season,
            STRING_AGG(DISTINCT gl.level, ', ') as levels
        FROM milb_game_logs gl
        WHERE gl.mlb_player_id NOT IN (
            SELECT mlb_player_id
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
        )
        GROUP BY gl.mlb_player_id
        ORDER BY game_count DESC
        LIMIT 10
    """)

    if non_prospects:
        print("Top 10 non-prospect players by game count:")
        print(f"{'Player ID':<15} {'Games':<8} {'Seasons':<12} {'Levels'}")
        print("-" * 80)
        for player in non_prospects:
            seasons = f"{player['first_season']}-{player['last_season']}"
            print(f"{player['mlb_player_id']:<15} {player['game_count']:<8} {seasons:<12} {player['levels']}")

        print(f"\n[OK] We have {len(non_prospects)} non-prospect players in the sample")
        print("     This confirms LEAGUE-WIDE data collection!")
    else:
        print("[WARN] No non-prospect players found - we may only have prospect data")

    # 4. Check if we have league-wide coverage for age-relative calculations
    print("\n\n[4] AGE-RELATIVE-TO-LEVEL FEASIBILITY CHECK")
    print("-" * 80)

    # Sample: How many players at AA in 2024?
    aa_2024 = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_player_id)
        FROM milb_game_logs
        WHERE level = 'AA' AND season = 2024
    """)

    print(f"Players at AA level in 2024: {aa_2024:,}")

    if aa_2024 > 100:
        print("[OK] Sufficient sample size for age-relative-to-level calculations")
        print("     We can calculate percentile rankings by age at each level!")
    else:
        print("[WARN] Small sample size - age-relative calculations may be noisy")

    # 5. Check specific level/season combinations
    print("\n\n[5] PLAYER COUNTS BY LEVEL & SEASON")
    print("-" * 80)

    level_season_counts = await conn.fetch("""
        SELECT
            season,
            level,
            COUNT(DISTINCT mlb_player_id) as players,
            COUNT(*) as games
        FROM milb_game_logs
        WHERE level IN ('AAA', 'AA', 'A+', 'A')
        GROUP BY season, level
        ORDER BY season DESC, level
    """)

    print(f"{'Season':<8} {'Level':<8} {'Players':<10} {'Games'}")
    print("-" * 80)
    for row in level_season_counts:
        print(f"{row['season']:<8} {row['level']:<8} {row['players']:<10,} {row['games']:,}")

    # 6. Age distribution check (if we have birth dates)
    print("\n\n[6] AGE DATA AVAILABILITY")
    print("-" * 80)

    # Check if we can derive age from game logs
    age_check = await conn.fetchrow("""
        SELECT
            COUNT(DISTINCT gl.mlb_player_id) as players_in_logs,
            COUNT(DISTINCT p.mlb_player_id) as players_with_birth_date
        FROM milb_game_logs gl
        LEFT JOIN prospects p ON gl.mlb_player_id = p.mlb_player_id AND p.birth_date IS NOT NULL
    """)

    print(f"Players in game logs: {age_check['players_in_logs']:,}")
    print(f"Players with birth dates (in prospects): {age_check['players_with_birth_date']:,}")
    coverage_pct = age_check['players_with_birth_date'] / age_check['players_in_logs'] * 100
    print(f"Birth date coverage: {coverage_pct:.1f}%")

    if age_check['players_with_birth_date'] < age_check['players_in_logs'] / 10:
        print("\n[MAJOR LIMITATION] We only have birth dates for our tracked prospects!")
        print("   We CANNOT calculate age for non-prospect players")
        print("   Age-relative-to-level will be LIMITED to comparing within our prospect pool")
        print("\n   RECOMMENDATION: We need to either:")
        print("   1. Collect birth date data for all MiLB players, OR")
        print("   2. Use alternative age proxies (draft year, years in minors)")
    else:
        print("\n[OK] We have good age coverage across all players")

    # 7. Final recommendation
    print("\n\n[7] SUMMARY & RECOMMENDATIONS")
    print("="*80)

    if game_log_players > prospect_count * 5:
        print("\n[DATA SCOPE] COMPREHENSIVE (League-wide MiLB data)")
        print(f"   - We have {game_log_players:,} players vs {prospect_count:,} prospects")
        print(f"   - Ratio: {game_log_players / prospect_count:.1f}x")
    else:
        print("\n[DATA SCOPE] PROSPECT-FOCUSED")
        print(f"   - We have {game_log_players:,} players vs {prospect_count:,} prospects")

    print("\nFOR AGE-RELATIVE-TO-LEVEL ADJUSTMENTS:")

    if age_check['players_with_birth_date'] < age_check['players_in_logs'] / 10:
        print("   [LIMITED] Birth dates only available for tracked prospects")
        print("   [ACTION NEEDED]")
        print("      - Option A: Scrape birth dates for all MiLB players from MLB API")
        print("      - Option B: Use draft year as age proxy")
        print("      - Option C: Calculate within-prospect-pool percentiles only")
        print("\n   [CURRENT CAPABILITY]")
        print("      - CAN compare prospects to each other (prospect percentiles)")
        print("      - CANNOT compare to true league-wide age distributions")
    else:
        print("   [FULL CAPABILITY] Can calculate true league-wide age percentiles")
        print("      - Compare each prospect to ALL players at their level")
        print("      - Generate percentile rankings by age at level")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_data_scope())
