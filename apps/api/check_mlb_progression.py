#!/usr/bin/env python3
"""Check MiLB to MLB progression data availability."""

import asyncio
from sqlalchemy import text
from app.db.database import AsyncSessionLocal


async def check_mlb_progression():
    """Analyze player progression from MiLB to MLB."""
    async with AsyncSessionLocal() as db:
        print("=" * 80)
        print("MiLB TO MLB PROGRESSION ANALYSIS")
        print("=" * 80)

        # Total unique players in MiLB
        result = await db.execute(text("""
            SELECT COUNT(DISTINCT mlb_player_id) as total_players
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
        """))
        total_milb_players = result.fetchone().total_players
        print(f"\nTotal MiLB Players: {total_milb_players:,}")

        # Players by level
        print("\nPlayers by MiLB Level:")
        result = await db.execute(text("""
            SELECT
                COALESCE(level, 'Unknown') as level,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as total_games
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'A-' THEN 5
                    WHEN 'ROK' THEN 6
                    ELSE 7
                END
        """))
        for row in result:
            print(f"  {row.level:10s}: {row.players:6,} players, {row.total_games:8,} games")

        # Top prospects by games played
        print("\nTop 10 Players by MiLB Games (Need MLB Data):")
        result = await db.execute(text("""
            SELECT
                mlb_player_id,
                COUNT(*) as games,
                COUNT(DISTINCT season) as seasons,
                MIN(season) as first_season,
                MAX(season) as last_season,
                prospect_id
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY mlb_player_id, prospect_id
            ORDER BY games DESC
            LIMIT 10
        """))

        print(f"  {'MLB ID':>10} | {'Games':>6} | {'Seasons':>7} | {'Years':>11} | {'Linked?':>8}")
        print("  " + "-" * 60)
        for row in result:
            linked = "Yes" if row.prospect_id else "No"
            years = f"{row.first_season}-{row.last_season}"
            print(f"  {row.mlb_player_id:>10} | {row.games:>6} | {row.seasons:>7} | {years:>11} | {linked:>8}")

        # Check for any MLB game logs table
        try:
            result = await db.execute(text("""
                SELECT COUNT(*) as count FROM information_schema.tables
                WHERE table_name = 'mlb_game_logs'
            """))
            if result.fetchone().count > 0:
                result = await db.execute(text("""
                    SELECT COUNT(DISTINCT mlb_player_id) as mlb_players
                    FROM mlb_game_logs
                """))
                mlb_players = result.fetchone().mlb_players
                print(f"\nMLB Game Logs: {mlb_players:,} players")
                overlap_pct = (mlb_players / total_milb_players) * 100
                print(f"MiLB->MLB Rate: {overlap_pct:.1f}%")
        except:
            print("\nWARNING: MLB Game Logs table does not exist!")

        # Year distribution
        print("\nMiLB Data by Year:")
        result = await db.execute(text("""
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as games
            FROM milb_game_logs
            WHERE mlb_player_id IS NOT NULL
            GROUP BY season
            ORDER BY season DESC
        """))
        for row in result:
            print(f"  {row.season}: {row.players:,} players, {row.games:,} games")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_mlb_progression())